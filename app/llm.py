"""Turn a category's articles into a few grounded, deduplicated stories.

Uses the Gemini API. The model only ever returns article numbers and never writes a link
itself: the numbers are validated and mapped back to the real URLs here.
"""
import json
import logging
import re
import time
from dataclasses import dataclass, field

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
- Write the headline and summary in {language}, whatever the language of the source articles."""

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
                },
                "required": ["title", "summary", "article_ids"],
            },
        }
    },
    "required": ["stories"],
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

    def to_dict(self) -> dict:
        return {"title": self.title, "summary": self.summary, "sources": self.sources,
                "single_source": self.single_source, "article_ids": self.article_ids}


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


def parse_stories(raw_stories, articles: list[dict], max_stories: int) -> list[Story]:
    """Validate the model output and map article numbers back to real URLs"""
    stories = []
    for raw in raw_stories if isinstance(raw_stories, list) else []:
        if not isinstance(raw, dict):
            continue
        title, summary = str(raw.get("title", "")).strip(), str(raw.get("summary", "")).strip()
        nums = []
        for n in raw.get("article_ids") or []:
            if isinstance(n, str) and n.strip().isdigit():
                n = int(n.strip())
            if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= len(articles) and n not in nums:
                nums.append(n)
        if not title or not summary or not nums:
            continue  # ungrounded story: drop it
        used = [articles[n - 1] for n in nums]
        sources, seen = [], set()
        for a in used:
            if a["source"] not in seen:
                seen.add(a["source"])
                sources.append({"name": a["source"], "url": a["url"]})
        stories.append(Story(title=title, summary=summary, sources=sources,
                             single_source=len(sources) == 1, article_ids=[a["id"] for a in used]))
        if len(stories) >= max_stories:
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

    def generate(self, system: str, prompt: str) -> tuple[dict, Usage]:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                # Headroom on purpose: "thinking" models spend output tokens on reasoning too
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json",
                "responseSchema": _to_gemini_schema(STORIES_SCHEMA),
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

    def summarize(self, category_label: str, articles: list[dict]) -> tuple[list[Story], Usage]:
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
        self._wait_turn()
        try:
            data, usage = self.client.generate(system, prompt)
        finally:
            self._last_call = time.monotonic()
        stories = parse_stories(data.get("stories", []), batch, self.max_stories)
        if not stories:
            raise LLMError("model returned no valid stories")
        log.info("%-24s %2d articles -> %d stories (%d in / %d out tokens) [%s]",
                 category_label, len(batch), len(stories), usage.input_tokens, usage.output_tokens, self.label)
        return stories, usage


def make_summarizer(s: Settings) -> Summarizer:
    client = GeminiClient(s.gemini_api_key, s.gemini_model)
    return Summarizer(client, s.digest_language, s.max_stories_per_category,
                      s.gemini_max_input, s.gemini_lead_chars, s.gemini_interval)
