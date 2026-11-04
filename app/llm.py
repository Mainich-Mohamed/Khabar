"""Turn a category's articles into a few grounded, deduplicated stories.

Uses the Gemini API. The model only ever returns article numbers and never writes a link
itself: the numbers are validated and mapped back to the real URLs here.
"""
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from urllib.parse import quote_plus

import httpx

from app.config import Settings

log = logging.getLogger(__name__)

# Shared by SYSTEM_PROMPT and UPDATE_PROMPT: fact rules and the new/update/repeat statuses
STORY_RULES = """Strict rules:
- Use ONLY facts stated in the provided articles. Never add outside knowledge, numbers, or quotes.
- If the articles disagree, say so briefly.
- If an article is only a headline with no text, stay general rather than guessing specifics.
- List in article_ids EVERY provided article number that covers the story.
- Order stories from most to least important.
- Write the headline and summary in {language}, whatever the language of the source articles.

You may also receive stories already emailed to the reader, numbered P1, P2, ... Set status on every story:
- "new": not covered by any previously sent story.
- "update": the same event as a previously sent story AND the articles add new facts. Set previous to
  that story's number (P3 -> 3) and start the summary with what changed.
- "repeat": the same event as a previously sent story and the articles add NO new fact. Set previous
  to that story's number.
Use "repeat" only when you are certain nothing new was reported. If you are unsure, use "update".
If no previously sent stories are given, every story is "new"."""

SYSTEM_PROMPT = """You are the editor of a concise personal news brief for a busy reader.

You receive numbered news articles from ONE category. Your job:
1. Group articles that cover the same event into ONE story (different outlets, same news = one story).
2. Select the most important stories: real-world impact first, then novelty. Skip minor, promotional,
   opinion-only, or duplicate items.
{style}

""" + STORY_RULES

UPDATE_PROMPT = """You are the editor of the short afternoon update of a personal news brief for a busy reader.
The reader got this morning's full brief, and a full brief comes this evening.

You receive numbered news articles from ALL categories. Your job:
1. Group articles that cover the same event into ONE story (different outlets, same news = one story).
2. Keep ONLY developments worth interrupting the reader's afternoon: major real-world impact, a turning
   point, or an important development in a story already sent. Return fewer stories than allowed if fewer
   qualify, and none if nothing qualifies. Never pad the list with minor items.
{style}

""" + STORY_RULES

# Rule 3 of SYSTEM_PROMPT and UPDATE_PROMPT, chosen by DIGEST_VOICE. "plain" is the original wording, kept to switch back
VOICES = {
    "plain": "3. For each story write a neutral headline and a 2-3 sentence summary: what happened, then why it matters.",
    "lively": """3. For each story write a headline and a 2-3 sentence summary, like a sharp, warm newsletter writer:
   - Headline: concrete and vivid, built on the most striking fact, with an active verb.
     No clickbait, no questions, no exclamation marks.
   - First sentence: the news itself, plain and direct. Then why it matters to the reader, in everyday words.
   - Prefer short sentences and concrete details from the articles (numbers, names, places) over abstractions.
   - A light touch of wit is welcome when the story allows it; never on deaths, disasters, violence or tragedy.
   - Avoid filler and cliches such as "amid", "in a move", "sparking concerns", "highlights the ongoing".""",
}

# Standard JSON Schema; converted to Gemini's OpenAPI-style dialect before sending
STORIES_SCHEMA = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Headline, max 14 words."},
                    "summary": {"type": "string", "description": "2-3 sentences: what happened, then why it matters."},
                    "article_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Numbers of ALL provided articles covering this story.",
                    },
                    "status": {"type": "string", "enum": ["new", "update", "repeat"],
                               "description": "new, update or repeat, compared with previously sent stories."},
                    "previous": {"type": "integer",
                                 "description": "Number of the previously sent story (P3 -> 3) for update or repeat."},
                },
                "required": ["title", "summary", "article_ids", "status"],
            },
        }
    },
    "required": ["stories"],
}

EDITOR_PROMPT = """You are the front-page editor of a concise personal news brief.

You receive numbered stories, already selected and summarized, from several categories.
Pick the ONE story that matters most to the reader today: real-world impact first, then novelty."""

LEAD_SCHEMA = {
    "type": "object",
    "properties": {
        "story": {"type": "integer", "description": "Number of the most important story."},
    },
    "required": ["story"],
}

ARRANGE_PROMPT = """You are the section editor of a concise personal news brief.

You receive the brief's stories, numbered, each with the section it is in now. They were written section
by section from news feeds, and a feed is filed under one section whatever it reports. So a story can sit in
the wrong section, and the same event can appear in two sections.

The sections:
{sections}

For EVERY story return:
- category: the key of the section it belongs in. Place it by its main subject; if two sections fit, by its
  main consequence. Keep its current section unless another one is clearly better.
- same_as: ONLY if it covers the same event as an EARLIER story in the list, that story's number. Otherwise omit it."""


def arrange_schema(keys: list[str]) -> dict:
    """Built per call: the category enum is the configured section keys"""
    return {
        "type": "object",
        "properties": {
            "stories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "story": {"type": "integer", "description": "Number of the story."},
                        "category": {"type": "string", "enum": keys, "description": "Key of its section."},
                        "same_as": {"type": "integer",
                                    "description": "Earlier story covering the same event, if any."},
                    },
                    "required": ["story", "category"],
                },
            }
        },
        "required": ["stories"],
    }

CURIOSITY_PROMPT = """You write the closing "Did you know?" item of a personal news brief.
Its job is to make the reader smile or think: a surprising, funny or insightful fact on ANY subject
(science, history, economics, technology, nature, language, culture...). It does not need to relate to the news.

Strict rules:
- Only well-established, widely documented facts. If you are not certain a fact is true, pick another one.
- No exact numbers, dates or quotes unless they are famous and well documented.
- Do not repeat or closely resemble any of the previous items you are given, and do not reuse their topics.
- Write the title and text in {language}. topic is the title of the English Wikipedia article that covers the fact."""

# One subject area is drawn per attempt so the model can't settle on a few favourites (it kept returning
# sea otters). Animals are just one area among many
CURIOSITY_AREAS = [
    "history", "geography and places", "language and words", "mathematics and logic",
    "the human body and medicine", "space and astronomy", "food and drink", "inventions and technology",
    "money and economics", "art, music and literature", "animals", "plants and nature",
    "physics and chemistry", "everyday objects and where they come from",
]
CURIOSITY_TRIES = 3     # the first item, plus up to two retries when its topic was already used

CURIOSITY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short catchy title, max 10 words."},
        "text": {"type": "string", "description": "2-3 sentences."},
        "topic": {"type": "string", "description": "English Wikipedia article title for the fact."},
    },
    "required": ["title", "text", "topic"],
}

EXPERT_PROMPT = """You are a senior analyst specialised in {label} ({description}). You write the section of
the "Khabar Artificial Expert", a weekly analysis for a reader who followed the daily news briefs all week and
now wants to understand what is really going on and where it leads.

You receive this week's stories in your field, numbered, in the order they were reported. Write ONE analysis
of 300 to 400 words in {language}, in 3 to 5 paragraphs of clear prose for a smart non-specialist:
- What is happening: the threads and patterns that connect the stories, not a list of them. Skip minor stories.
- Why: the causes and forces behind it. Use your expertise: history, precedents, how markets, states,
  institutions or technologies usually behave.
- What it means: the consequences, and what to watch next as scenarios ("if this continues, expect..."),
  never as certainties.

Strict rules:
- Every event, number, name or quote you mention must come from the stories. Never add events or current
  facts from memory: your knowledge of the present may be out of date.
- Write your own reasoning as reasoning ("this suggests", "the risk is"), not as established fact.
- No bullet points and no headings inside the analysis.
- In story_ids list the numbers of the stories your analysis relies on most, at most 6."""

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "A sharp title for the week in this field, max 12 words."},
        "paragraphs": {"type": "array", "items": {"type": "string"},
                       "description": "3 to 5 paragraphs, 300 to 400 words in total."},
        "story_ids": {"type": "array", "items": {"type": "integer"},
                      "description": "Numbers of the stories the analysis relies on most, at most 6."},
    },
    "required": ["title", "paragraphs", "story_ids"],
}
MAX_REFERENCES = 6      # the "Based on" list under each analysis


class LLMError(RuntimeError):
    """Any provider failure. The summarizer moves on to the next provider, then to headlines"""


class QuotaExhausted(LLMError):
    """Daily free quota used up: retrying today is pointless"""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens


@dataclass
class Story:
    title: str
    summary: str
    sources: list[dict]            # [{"name": ..., "url": ...}], one per outlet
    single_source: bool
    article_ids: list[int] = field(default_factory=list)   # DB ids, for traceability
    status: str = "new"                    # new | update | repeat (repeats are dropped by the pipeline)
    previous_title: str | None = None      # headline of the earlier story, for update and repeat

    def to_dict(self) -> dict:
        return {"title": self.title, "summary": self.summary, "sources": self.sources,
                "single_source": self.single_source, "article_ids": self.article_ids,
                "status": self.status, "previous_title": self.previous_title}


@dataclass
class Curiosity:
    title: str
    text: str
    topic: str     # Wikipedia article title: we build the link, the model never writes one

    @property
    def url(self) -> str:
        return "https://en.wikipedia.org/w/index.php?search=" + quote_plus(self.topic)

    def to_dict(self) -> dict:
        return {"title": self.title, "text": self.text, "topic": self.topic, "url": self.url}


@dataclass
class Analysis:
    title: str
    paragraphs: list[str]
    references: list[dict]     # [{"title": ..., "sources": [...]}]: stories the analysis relies on, real URLs

    @property
    def words(self) -> int:
        return sum(len(p.split()) for p in self.paragraphs)

    def to_dict(self) -> dict:
        return {"title": self.title, "paragraphs": self.paragraphs, "references": self.references}


# --------------------------------------------------------------------------- helpers
def format_articles(articles: list[dict], lead_chars: int = 900) -> str:
    blocks = []
    for i, a in enumerate(articles, start=1):
        body = (a.get("lead") or a.get("summary") or "(headline only)")[:lead_chars]
        blocks.append(
            f"[{i}] Source: {a['source']} | Published: {a['published_at']:%Y-%m-%d %H:%M} UTC\n"
            f"Title: {a['title']}\n"
            f"Text: {body}"
        )
    return "\n\n".join(blocks)


def format_previous(previous: list[dict]) -> str:
    return "\n".join(f"P{i}. {p['title']}" + (f" | {p['summary']}" if p.get("summary") else "")
                     for i, p in enumerate(previous, start=1))


def format_candidates(candidates: list[tuple[str, Story]]) -> str:
    """Stories already summarized, numbered from 1, for the front-page editor"""
    return "\n\n".join(f"[{i}] Category: {label}\nTitle: {st.title}\nSummary: {st.summary}"
                       for i, (label, st) in enumerate(candidates, start=1))


def format_week_stories(stories: list[dict]) -> str:
    """The week's sent stories, numbered from 1, with their day and update chain, for the expert"""
    blocks = []
    for i, st in enumerate(stories, start=1):
        head = f"[{i}] {st['sent_at']:%a %d %b}"
        if st.get("status") == "update" and st.get("previous_title"):
            head += f" | Update of: {st['previous_title']}"
        blocks.append(f"{head}\nTitle: {st['title']}\nSummary: {st['summary']}")
    return "\n\n".join(blocks)


def parse_json_text(text: str) -> dict:
    """Parse model text as JSON, tolerating <think> blocks, code fences or stray text around it"""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise LLMError(f"no JSON object in model output: {text[:200]!r}")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"invalid JSON from model: {exc}") from exc


def _valid_number(n, count: int) -> int | None:
    """1-based reference from the model: an int (or digit string) within range, else None"""
    if isinstance(n, str) and n.strip().isdigit():
        n = int(n.strip())
    if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= count:
        return n
    return None


def parse_stories(raw_stories, articles: list[dict], max_stories: int,
                  previous: list[dict] | None = None) -> list[Story]:
    """Validate the model output and map article numbers back to real URLs.
    Update and repeat must point at a real previous story; otherwise the story is kept as new"""
    previous = previous or []
    stories, kept = [], 0
    for raw in raw_stories if isinstance(raw_stories, list) else []:
        if not isinstance(raw, dict):
            continue
        title, summary = str(raw.get("title", "")).strip(), str(raw.get("summary", "")).strip()
        nums = []
        for n in raw.get("article_ids") or []:
            n = _valid_number(n, len(articles))
            if n is not None and n not in nums:
                nums.append(n)
        if not title or not summary or not nums:
            continue  # ungrounded story: drop it
        status, previous_title = str(raw.get("status", "")).strip().lower(), None
        p = _valid_number(raw.get("previous"), len(previous))
        if status in ("update", "repeat") and p is not None:
            previous_title = previous[p - 1]["title"]
        else:
            status = "new"   # unknown status, or update/repeat without a real previous story: keep it
        used = [articles[n - 1] for n in nums]
        sources, seen = [], set()
        for a in used:
            if a["source"] not in seen:
                seen.add(a["source"])
                sources.append({"name": a["source"], "url": a["url"]})
        stories.append(Story(title=title, summary=summary, sources=sources,
                             single_source=len(sources) == 1, article_ids=[a["id"] for a in used],
                             status=status, previous_title=previous_title))
        if status != "repeat":
            kept += 1
            if kept >= max_stories:
                break
    return stories


@dataclass
class Placement:
    category: str                 # section key the story belongs in
    same_as: int | None = None    # 0-based index of an earlier story covering the same event


def parse_arrangement(raw, current: list[str], keys: list[str]) -> list[Placement]:
    """One placement per story, in input order. Anything missing or invalid keeps the story where it is"""
    placements = [Placement(c) for c in current]
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        n = _valid_number(item.get("story"), len(current))
        if n is None:
            continue
        category = str(item.get("category", "")).strip()
        if category in keys:
            placements[n - 1].category = category
        same = _valid_number(item.get("same_as"), len(current))
        if same is not None and same < n:      # earlier only: no self-merge, no loops
            placements[n - 1].same_as = same - 1
    return placements


def parse_analysis(data: dict, stories: list[dict]) -> Analysis:
    """Validate the expert's answer; story numbers become the real stories (titles and links).
    An analysis without valid references is kept: it is still worth reading"""
    title = (data.get("title") or "").strip()
    paragraphs = [p.strip() for p in data.get("paragraphs") or [] if isinstance(p, str) and p.strip()]
    if not title or not paragraphs:
        raise LLMError(f"expert returned no analysis: {str(data)[:200]}")
    refs, seen = [], set()
    for raw in data.get("story_ids") or []:
        n = _valid_number(raw, len(stories))
        if n is not None and n not in seen and len(refs) < MAX_REFERENCES:
            seen.add(n)
            refs.append({"title": stories[n - 1]["title"], "sources": stories[n - 1]["sources"]})
    return Analysis(title=title, paragraphs=paragraphs, references=refs)


def _norm(text) -> str:
    return " ".join(str(text or "").lower().split())


def _curiosity_item(data: dict) -> Curiosity:
    title, text, topic = (str(data.get(k, "")).strip() for k in ("title", "text", "topic"))
    if not (title and text and topic):
        raise LLMError("curiosity call returned an incomplete item")
    return Curiosity(title, text, topic)


def _to_gemini_schema(schema: dict) -> dict:
    """Gemini's responseSchema uses an OpenAPI subset with upper-case type names"""
    out = {}
    for k, v in schema.items():
        if k == "type":
            out[k] = v.upper()
        elif k == "properties":
            out[k] = {name: _to_gemini_schema(sub) for name, sub in v.items()}
        elif k == "items":
            out[k] = _to_gemini_schema(v)
        else:
            out[k] = v
    return out


def _retry_delay(error_body: dict) -> float | None:
    """Gemini puts the 'retry in N seconds' hint in error.details[].retryDelay"""
    for d in error_body.get("error", {}).get("details", []) or []:
        if str(d.get("@type", "")).endswith("RetryInfo") and d.get("retryDelay"):
            try:
                return float(str(d["retryDelay"]).rstrip("s"))
            except ValueError:
                return None
    return None


# --------------------------------------------------------------------------- Gemini client
class GeminiClient:
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, model: str, client: httpx.Client | None = None):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set (create one free at aistudio.google.com)")
        self.model = model
        self.client = client or httpx.Client(timeout=120)
        self.headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    def generate(self, system: str, prompt: str, schema: dict = STORIES_SCHEMA,
                 temperature: float = 0.2) -> tuple[dict, Usage]:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                # Headroom on purpose: "thinking" models spend output tokens on reasoning too
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json",
                "responseSchema": _to_gemini_schema(schema),
            },
        }
        url = self.URL.format(model=self.model)
        for attempt in range(1, 4):
            try:
                r = self.client.post(url, headers=self.headers, json=body)
            except httpx.TransportError as exc:
                if attempt == 3:
                    raise LLMError(f"Gemini unreachable: {exc}") from exc
                time.sleep(5 * attempt)
                continue

            if r.status_code == 200:
                return self._parse(r.json())

            try:
                err = r.json()
            except ValueError:
                err = {}
            message = err.get("error", {}).get("message", r.text[:300])
            if r.status_code == 429:
                if "PerDay" in r.text or "per day" in message.lower():
                    raise QuotaExhausted(f"Gemini daily free quota used up: {message}")
                wait = min(_retry_delay(err) or 20 * attempt, 65)
                log.warning("Gemini rate limit (attempt %d), waiting %.0fs", attempt, wait)
                if attempt < 3:
                    time.sleep(wait)
                    continue
            elif r.status_code in (500, 502, 503, 504) and attempt < 3:
                time.sleep(10 * attempt)
                continue
            hint = ""
            if r.status_code in (400, 401, 403) and re.search(r"api key|API_KEY|permission", r.text, re.I):
                hint = " (check GEMINI_API_KEY)"
            elif r.status_code == 404:
                hint = " (check GEMINI_MODEL: that model name is not available to this key)"
            raise LLMError(f"Gemini HTTP {r.status_code}: {message}{hint}")
        raise LLMError("Gemini failed after retries")

    @staticmethod
    def _parse(data: dict) -> tuple[dict, Usage]:
        meta = data.get("usageMetadata", {})
        usage = Usage(meta.get("promptTokenCount", 0),
                      meta.get("candidatesTokenCount", 0) + meta.get("thoughtsTokenCount", 0))
        if data.get("promptFeedback", {}).get("blockReason"):
            raise LLMError(f"Gemini blocked the prompt: {data['promptFeedback']['blockReason']}")
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMError("Gemini returned no candidates")
        cand = candidates[0]
        text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []) if not p.get("thought"))
        if cand.get("finishReason") == "MAX_TOKENS":
            raise LLMError("Gemini output was cut off (MAX_TOKENS); lower MAX_STORIES_PER_CATEGORY")
        return parse_json_text(text), usage


# --------------------------------------------------------------------------- summarizer
class Summarizer:
    """Turns one category's articles into stories with Gemini. Raises LLMError (or QuotaExhausted
    when the daily free quota is gone) so the pipeline can fall back to plain headlines"""

    def __init__(self, client: GeminiClient, language: str, max_stories: int,
                 max_input: int, lead_chars: int, interval: float, voice: str):
        self.client, self.language, self.max_stories = client, language, max_stories
        self.max_input, self.lead_chars, self.interval = max_input, lead_chars, interval
        self.voice = voice
        self._last_call: float | None = None

    @property
    def label(self) -> str:
        return f"gemini:{self.client.model}"

    def _wait_turn(self) -> None:
        if self._last_call is not None:
            wait = self.interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)   # stay under the free tier's per-minute limit

    def _call(self, system: str, prompt: str, **kw) -> tuple[dict, Usage]:
        self._wait_turn()
        try:
            return self.client.generate(system, prompt, **kw)
        finally:
            self._last_call = time.monotonic()

    def summarize(self, category_label: str, articles: list[dict],
                  previous: list[dict] | None = None) -> tuple[list[Story], Usage]:
        system = SYSTEM_PROMPT.format(language=self.language, style=VOICES[self.voice])
        batch = articles[: self.max_input]
        prompt = "\n".join([
            f"Category: {category_label}",
            f"Return at most {self.max_stories} stories.",
            "",
            "Articles:",
            "",
            format_articles(batch, self.lead_chars),
        ])
        if previous:
            prompt += "\n\nPreviously sent stories:\n\n" + format_previous(previous)
        data, usage = self._call(system, prompt)
        stories = parse_stories(data.get("stories", []), batch, self.max_stories, previous)
        if not stories:
            raise LLMError("model returned no valid stories")
        updates = sum(st.status == "update" for st in stories)
        repeats = sum(st.status == "repeat" for st in stories)
        log.info("%-24s %2d articles -> %d stories, updates=%d repeats=%d (%d in / %d out tokens) [%s, %s]",
                 category_label, len(batch), len(stories), updates, repeats,
                 usage.input_tokens, usage.output_tokens, self.label, self.voice)
        return stories, usage

    def highlights(self, articles: list[dict], previous: list[dict] | None = None,
                   max_stories: int = 5) -> tuple[list[Story], Usage]:
        """The few developments worth an afternoon email, across all categories. May be empty"""
        system = UPDATE_PROMPT.format(language=self.language, style=VOICES[self.voice])
        prompt = "\n".join([
            f"Return at most {max_stories} stories, or none.",
            "",
            "Articles:",
            "",
            format_articles(articles, self.lead_chars),
        ])
        if previous:
            prompt += "\n\nPreviously sent stories:\n\n" + format_previous(previous)
        data, usage = self._call(system, prompt)
        if not isinstance(data.get("stories"), list):
            raise LLMError(f"update call returned no story list: {str(data)[:200]}")
        stories = parse_stories(data["stories"], articles, max_stories, previous)
        log.info("Update: %d articles -> %d stories, repeats=%d (%d in / %d out tokens) [%s, %s]",
                 len(articles), len(stories), sum(st.status == "repeat" for st in stories),
                 usage.input_tokens, usage.output_tokens, self.label, self.voice)
        return stories, usage

    def pick_lead(self, candidates: list[tuple[str, Story]]) -> tuple[int, Usage]:
        """Index (0-based) of the most important story across categories"""
        data, usage = self._call(EDITOR_PROMPT, "Stories:\n\n" + format_candidates(candidates), schema=LEAD_SCHEMA)
        n = _valid_number(data.get("story"), len(candidates))
        if n is None:
            raise LLMError(f"editor returned no valid lead: {str(data)[:200]}")
        log.info("Top story: %r (%d in / %d out tokens)", candidates[n - 1][1].title,
                 usage.input_tokens, usage.output_tokens)
        return n - 1, usage

    def arrange(self, stories: list[tuple[str, Story]],
                sections: dict[str, str]) -> tuple[list[Placement], Usage]:
        """Right section for each story, and which ones repeat an earlier story. stories: (section key, story)
        in brief order; sections: key -> "Label: what belongs there". The model returns numbers and keys only"""
        keys = list(sections)
        system = ARRANGE_PROMPT.format(sections="\n".join(f"- {k}: {d}" for k, d in sections.items()))
        data, usage = self._call(system, "Stories:\n\n" + format_candidates(stories), schema=arrange_schema(keys))
        if not isinstance(data.get("stories"), list):
            raise LLMError(f"arrange call returned no story list: {str(data)[:200]}")
        placements = parse_arrangement(data["stories"], [k for k, _ in stories], keys)
        moved = sum(p.category != k for p, (k, _) in zip(placements, stories))
        merged = sum(p.same_as is not None for p in placements)
        log.info("Arrange: %d stories, %d moved, %d merged (%d in / %d out tokens)",
                 len(stories), moved, merged, usage.input_tokens, usage.output_tokens)
        return placements, usage

    def curiosity(self, previous: list[dict]) -> tuple[Curiosity, Usage]:
        """A general-knowledge "Did you know?" item on a topic not used recently. When the model keeps
        returning a used topic, the last item is kept anyway: a repeat is better than no item"""
        used = {_norm(p["topic"]) for p in previous if p.get("topic")}
        history = "\n".join(f"- {p['title']}" + (f" (topic: {p['topic']})" if p.get("topic") else "")
                            for p in previous)
        system = CURIOSITY_PROMPT.format(language=self.language)
        areas = random.sample(CURIOSITY_AREAS, CURIOSITY_TRIES)        # distinct: a retry changes the subject
        total, item = Usage(), None
        for attempt, area in enumerate(areas, start=1):
            prompt = f"Write today's item. Subject area: {area}."
            if history:
                prompt += "\n\nPrevious items (do not repeat these or reuse their topics):\n" + history
            try:
                # A little more randomness than the news calls, for variety from one email to the next
                data, usage = self._call(system, prompt, schema=CURIOSITY_SCHEMA, temperature=0.7)
                candidate = _curiosity_item(data)
            except LLMError:
                if item is None:
                    raise
                break                                                   # a retry failed: keep the item we have
            total.add(usage)
            item = candidate
            log.info("Curiosity: %r [%s] (%d in / %d out tokens)", item.title, area,
                     usage.input_tokens, usage.output_tokens)
            if _norm(item.topic) not in used:
                break
            log.warning("Curiosity %r repeats the topic %r (attempt %d of %d)",
                        item.title, item.topic, attempt, CURIOSITY_TRIES)
        return item, total

    def expert(self, label: str, description: str, stories: list[dict]) -> tuple[Analysis, Usage]:
        """One section of the weekly analysis: what happened in this field this week, and what it means"""
        system = EXPERT_PROMPT.format(label=label, description=description, language=self.language)
        # A little more freedom than the news calls (0.2): this is reasoning, not reporting
        data, usage = self._call(system, "This week's stories:\n\n" + format_week_stories(stories),
                                 schema=ANALYSIS_SCHEMA, temperature=0.4)
        analysis = parse_analysis(data, stories)
        log.info("Expert %-22s %2d stories -> %d words, %d references (%d in / %d out tokens) [%s]",
                 label, len(stories), analysis.words, len(analysis.references),
                 usage.input_tokens, usage.output_tokens, self.label)
        return analysis, usage


def make_summarizer(s: Settings, model: str | None = None) -> Summarizer:
    """model overrides GEMINI_MODEL: the weekly analysis passes s.gemini_weekly_model"""
    client = GeminiClient(s.gemini_api_key, model or s.gemini_model)
    return Summarizer(client, s.digest_language, s.max_stories_per_category,
                      s.gemini_max_input, s.gemini_lead_chars, s.gemini_interval, s.digest_voice)
