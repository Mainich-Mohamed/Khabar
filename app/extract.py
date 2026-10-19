"""Fetch the lead paragraphs of articles so the LLM summarizes real text, not just headlines"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import trafilatura

from app.ingest import get_with_retry, make_client

log = logging.getLogger(__name__)

LEAD_CHARS = 900           # ~3 paragraphs: enough to summarize, cheap to send
MAX_WORKERS = 8
# Google News links are encoded redirects that a plain HTTP client usually can't resolve,
# and aggregators (HN, Lobsters) point at arbitrary sites. Use the RSS title/snippet for these
SKIP_HOSTS = {"news.google.com"}

# trafilatura (lxml/C) causes heap corruption under thread parallelism
# Lock serializes parsing while downloads remain parallel
_PARSE_LOCK = threading.Lock()


def _lead_from_html(html: str) -> str | None:
    with _PARSE_LOCK:
        text = trafilatura.extract(html, include_comments=False, include_tables=False,
                                   favor_precision=True, deduplicate=True)
    if not text:
        return None
    paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 40]
    if not paragraphs:
        return text.strip()[:LEAD_CHARS] or None
    lead = ""
    for p in paragraphs:
        if lead and len(lead) + len(p) > LEAD_CHARS:
            break
        lead += p[:LEAD_CHARS] + "\n"
    return lead.strip()


def _fetch_one(client, article: dict) -> tuple[int, str | None, str]:
    if urlsplit(article["url"]).hostname in SKIP_HOSTS:
        return article["id"], None, "skipped"
    try:
        resp = get_with_retry(client, article["url"], attempts=2)
        if resp.status_code != 200 or "html" not in resp.headers.get("content-type", ""):
            return article["id"], None, "failed"
        lead = _lead_from_html(resp.text)
        return article["id"], lead, "ok" if lead else "failed"
    except Exception as exc:
        log.debug("extract failed for %s: %s", article["url"], exc)
        return article["id"], None, "failed"


def extract_leads(conn, articles: list[dict], save) -> None:
    """Fill `lead` for articles that don't have one yet (results are cached in the DB)"""
    todo = [a for a in articles if not a.get("lead_status")]
    if not todo:
        return
    ok = 0
    with make_client() as client, ThreadPoolExecutor(MAX_WORKERS) as pool:
        for article_id, lead, status in pool.map(lambda a: _fetch_one(client, a), todo):
            save(conn, article_id, lead, status)
            ok += status == "ok"
            for a in articles:  # keep the in-memory rows in sync
                if a["id"] == article_id:
                    a["lead"], a["lead_status"] = lead, status
    log.info("Lead extraction: %d/%d articles extracted", ok, len(todo))
