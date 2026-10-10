import calendar
import html
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import httpx

from app.config import Source

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; news-digest/0.2; personal project)"}
TRACKING_KEYS = {"fbclid", "gclid", "ref", "cmpid", "ocid", "at_medium", "at_campaign"}
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def normalize_url(url: str) -> str:
    """Strip tracking params and fragments so the same article isn't stored twice"""
    p = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in TRACKING_KEYS]
    return urlunsplit((p.scheme, p.netloc.lower(), p.path, urlencode(query), ""))


def clean_text(raw: str | None, limit: int = 600) -> str:
    if not raw:
        return ""
    text = WS_RE.sub(" ", html.unescape(TAG_RE.sub(" ", raw))).strip()
    return text[:limit]


def entry_time(entry) -> datetime:
    now = datetime.now(timezone.utc)
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return now
    ts = datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
    return min(ts, now)  # some feeds publish future timestamps


def get_with_retry(client: httpx.Client, url: str, attempts: int = 3) -> httpx.Response:
    """Retry network/TLS/timeout errors (not HTTP 4xx/5xx) with a short backoff"""
    for attempt in range(attempts):
        try:
            return client.get(url)
        except httpx.TransportError:
            if attempt == attempts - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def fetch_feed(client: httpx.Client, source: Source) -> list[dict]:
    resp = get_with_retry(client, source.url)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        raise ValueError(f"unparseable feed: {feed.bozo_exception}")

    articles = []
    for e in feed.entries:
        link, title = e.get("link"), clean_text(e.get("title"), 300)
        if not link or not title:
            continue
        articles.append({
            "source": source.name,
            "category": source.category,
            "url": normalize_url(link),
            "title": title,
            "summary": clean_text(e.get("summary")),
            "lang": source.lang,
            "published_at": entry_time(e),
        })
    return articles


def make_client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True)


def ingest_all(conn, sources: list[Source], insert) -> tuple[int, list[str]]:
    """Fetch every source and store new articles. One bad feed never stops the run"""
    total_new, errors = 0, []
    with make_client() as client:
        for src in sources:
            try:
                items = fetch_feed(client, src)
                new = sum(insert(conn, a) for a in items)
                total_new += new
                log.info("%-18s %3d items, %3d new", src.name, len(items), new)
            except Exception as exc:  # noqa: BLE001 - log and continue
                msg = f"{src.name}: {type(exc).__name__}: {exc}"
                errors.append(msg)
                log.warning("FAILED %s", msg)
    return total_new, errors
