import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.config import Source
from app.ingest import clean_text, entry_time, fetch_feed, get_with_retry, ingest_all, normalize_url

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Feed</title>
  <item>
    <title>First &amp; <b>bold</b> story</title>
    <link>https://Example.com/a?utm_source=rss&amp;id=1#top</link>
    <description>&lt;p&gt;Hello   <![CDATA[<i>world</i>]]>&lt;/p&gt;</description>
    <pubDate>Mon, 05 Oct 2026 10:00:00 GMT</pubDate>
  </item>
  <item><title>No link here</title></item>
  <item><link>https://example.com/no-title</link></item>
  <item><title>Undated</title><link>https://example.com/b</link></item>
</channel></rss>"""

SRC = Source(name="Test", url="https://feed.test/rss", category="tech", lang="fr")


# --------------------------------------------------------------------------- normalize_url
@pytest.mark.parametrize("raw, expected", [
    ("https://Example.COM/path?utm_source=x&utm_medium=y&id=3#frag", "https://example.com/path?id=3"),
    ("https://x.com/a?fbclid=1&gclid=2&ref=3&keep=4", "https://x.com/a?keep=4"),
    ("https://x.com/a?UTM_Campaign=z", "https://x.com/a"),
    ("  https://x.com/a  ", "https://x.com/a"),
    ("https://x.com/a?empty=", "https://x.com/a?empty="),
])
def test_normalize_url(raw, expected):
    assert normalize_url(raw) == expected


def test_normalize_url_keeps_path_case():
    assert normalize_url("https://X.com/Some/Path") == "https://x.com/Some/Path"


# --------------------------------------------------------------------------- clean_text
def test_clean_text_strips_tags_entities_whitespace():
    assert clean_text("<p>Tom &amp; Jerry</p>\n\n  <b>run</b>") == "Tom & Jerry run"


def test_clean_text_limit_and_empty():
    assert clean_text("abcdef", limit=3) == "abc"
    assert clean_text(None) == ""
    assert clean_text("") == ""


# --------------------------------------------------------------------------- entry_time
def test_entry_time_uses_published_then_updated():
    t = time.strptime("2026-10-05 10:00", "%Y-%m-%d %H:%M")
    assert entry_time({"published_parsed": t}) == datetime(2026, 10, 5, 10, tzinfo=timezone.utc)
    assert entry_time({"updated_parsed": t}) == datetime(2026, 10, 5, 10, tzinfo=timezone.utc)


def test_entry_time_missing_is_now():
    assert abs(entry_time({}) - datetime.now(timezone.utc)) < timedelta(seconds=5)


def test_entry_time_future_is_clamped_to_now():
    future = (datetime.now(timezone.utc) + timedelta(days=2)).timetuple()
    assert entry_time({"published_parsed": future}) <= datetime.now(timezone.utc)


# --------------------------------------------------------------------------- get_with_retry
def test_get_with_retry_recovers_from_transport_error(mock_client):
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, text="ok")

    assert get_with_retry(mock_client(handler), "https://x").text == "ok"
    assert len(calls) == 3


def test_get_with_retry_gives_up(mock_client):
    def handler(req):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(httpx.ReadTimeout):
        get_with_retry(mock_client(handler), "https://x", attempts=2)


def test_get_with_retry_does_not_retry_http_errors(mock_client):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503)

    assert get_with_retry(mock_client(handler), "https://x").status_code == 503
    assert len(calls) == 1


# --------------------------------------------------------------------------- fetch_feed
def test_fetch_feed_parses_and_cleans(mock_client):
    client = mock_client(lambda req: httpx.Response(200, text=RSS))
    items = fetch_feed(client, SRC)

    assert [i["url"] for i in items] == ["https://example.com/a?id=1", "https://example.com/b"]
    first = items[0]
    assert first["title"] == "First & bold story"
    assert "world" in first["summary"] and "<" not in first["summary"]
    assert first["source"] == "Test" and first["category"] == "tech" and first["lang"] == "fr"
    assert first["published_at"] == datetime(2026, 10, 5, 10, tzinfo=timezone.utc)


def test_fetch_feed_http_error_raises(mock_client):
    client = mock_client(lambda req: httpx.Response(404))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_feed(client, SRC)


def test_fetch_feed_garbage_raises(mock_client):
    client = mock_client(lambda req: httpx.Response(200, text="<html>not a feed"))
    with pytest.raises(ValueError, match="unparseable"):
        fetch_feed(client, SRC)


# --------------------------------------------------------------------------- ingest_all
def test_ingest_all_one_bad_feed_does_not_stop_the_run(monkeypatch):
    good = Source(name="Good", url="https://good/rss", category="tech")
    bad = Source(name="Bad", url="https://bad/rss", category="tech")

    def fake_fetch(client, src):
        if src is bad:
            raise ValueError("unparseable feed")
        return [{"url": "u1"}, {"url": "u2"}, {"url": "u3"}]

    monkeypatch.setattr("app.ingest.fetch_feed", fake_fetch)
    inserted = []

    def insert(conn, a):
        inserted.append(a["url"])
        return a["url"] != "u2"   # u2 already stored

    new, errors = ingest_all(None, [bad, good], insert)
    assert new == 2
    assert inserted == ["u1", "u2", "u3"]
    assert errors == ["Bad: ValueError: unparseable feed"]
