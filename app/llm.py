"""Turn a category's articles into a few grounded, deduplicated stories.

Uses the Gemini API. The model only ever returns article numbers and never writes a link
itself: the numbers are validated and mapped back to the real URLs here.
"""
import json
import logging
import re
import time
from dataclasses import dataclass, field
from urllib.parse import quote_plus

import httpx

from app.config import Settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the editor of a concise personal news brief for a busy reader.

You receive numbered news articles from ONE category. Your job:
1. Group articles that cover the same event into ONE story (different outlets, same news = one story).
2. Select the most important stories: real-world impact first, then novelty. Skip minor, promotional,
   opinion-only, or duplicate items.
3. For each story write a neutral headline and a 2-3 sentence summary: what happened, then why it matters.

Strict rules:
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

# Standard JSON Schema; converted to Gemini's OpenAPI-style dialect before sending
STORIES_SCHEMA = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Neutral, factual headline, max 14 words."},
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
Pick the ONE story that matters most to the reader today: real-world impact first, then novelty.
Then write ONE sentence on why it matters.

Strict rules:
- Use ONLY facts stated in the provided stories. Never add outside knowledge, numbers, or quotes.
- Write the sentence in {language}."""

LEAD_SCHEMA = {
    "type": "object",
    "properties": {
        "story": {"type": "integer", "description": "Number of the most important story."},
        "why_it_matters": {"type": "string", "description": "One sentence: why this story matters."},
    },
    "required": ["story", "why_it_matters"],
}

CURIOSITY_PROMPT = """You write the closing "Did you know?" item of a personal news brief.
Its job is to make the reader smile or think: a surprising, funny or insightful fact on ANY subject
(science, history, economics, technology, nature, language, culture...). It does not need to relate to the news.

Strict rules:
- Only well-established, widely documented facts. If you are not certain a fact is true, pick another one.
- No exact numbers, dates or quotes unless they are famous and well documented.
- Do not repeat or closely resemble any of the previous items you are given.
- Write the title and text in {language}. topic is the title of the English Wikipedia article that covers the fact."""

CURIOSITY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short catchy title, max 10 words."},
        "text": {"type": "string", "description": "2-3 sentences."},
        "topic": {"type": "string", "description": "English Wikipedia article title for the fact."},
    },
    "required": ["title", "text", "topic"],
}


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
                 max_input: int, lead_chars: int, interval: float):
        self.client, self.language, self.max_stories = client, language, max_stories
        self.max_input, self.lead_chars, self.interval = max_input, lead_chars, interval
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
        system = SYSTEM_PROMPT.format(language=self.language)
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
        log.info("%-24s %2d articles -> %d stories, updates=%d repeats=%d (%d in / %d out tokens) [%s]",
                 category_label, len(batch), len(stories), updates, repeats,
                 usage.input_tokens, usage.output_tokens, self.label)
        return stories, usage

    def pick_lead(self, candidates: list[tuple[str, Story]]) -> tuple[int, str, Usage]:
        """Index (0-based) of the most important story across categories, and why it matters"""
        system = EDITOR_PROMPT.format(language=self.language)
        data, usage = self._call(system, "Stories:\n\n" + format_candidates(candidates), schema=LEAD_SCHEMA)
        n = _valid_number(data.get("story"), len(candidates))
        why = str(data.get("why_it_matters", "")).strip()
        if n is None or not why:
            raise LLMError(f"editor returned no valid lead: {str(data)[:200]}")
        log.info("Top story: %r (%d in / %d out tokens)", candidates[n - 1][1].title,
                 usage.input_tokens, usage.output_tokens)
        return n - 1, why, usage

    def curiosity(self, previous_titles: list[str]) -> tuple[Curiosity, Usage]:
        """A general-knowledge "Did you know?" item, different from the recent ones"""
        system = CURIOSITY_PROMPT.format(language=self.language)
        prompt = "Write today's item."
        if previous_titles:
            prompt += "\n\nPrevious items (do not repeat):\n" + "\n".join(f"- {t}" for t in previous_titles)
        # A little more randomness than the news calls, for variety from one email to the next
        data, usage = self._call(system, prompt, schema=CURIOSITY_SCHEMA, temperature=0.7)
        title, text, topic = (str(data.get(k, "")).strip() for k in ("title", "text", "topic"))
        if not (title and text and topic):
            raise LLMError("curiosity call returned an incomplete item")
        log.info("Curiosity: %r (%d in / %d out tokens)", title, usage.input_tokens, usage.output_tokens)
        return Curiosity(title, text, topic), usage


def make_summarizer(s: Settings) -> Summarizer:
    client = GeminiClient(s.gemini_api_key, s.gemini_model)
    return Summarizer(client, s.digest_language, s.max_stories_per_category,
                      s.gemini_max_input, s.gemini_lead_chars, s.gemini_interval)
