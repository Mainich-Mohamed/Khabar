"""DB integration tests: run app/db.py against a real Postgres (pgvector image).

Opt-in: set TEST_DATABASE_URL to a throwaway database, for example
    docker run --rm -d --name khabar-testdb -p 5434:5432 -e POSTGRES_USER=test \
        -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test pgvector/pgvector:pg16
    TEST_DATABASE_URL=postgresql://test:test@localhost:5434/test pytest tests/test_db.py
Every test empties the tables, so never point this at a database you care about.
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import db

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB_URL:
    pytest.skip("TEST_DATABASE_URL not set: skipping DB integration tests", allow_module_level=True)

INIT_SQL = Path(__file__).resolve().parent.parent.parent / "db" / "init.sql"
        
# --------------------------------------------------------------------------- fixtures
@pytest.fixture(scope="session")
def schema_conn():
    """One connection for the whole run, with the schema built the way production builds it"""
    conn = db.connect(TEST_DB_URL)
    if "test" not in conn.info.dbname:
        conn.close()
        pytest.fail(f"refusing to run: database {conn.info.dbname!r} has no 'test' in its name")
    conn.execute(INIT_SQL.read_text(encoding="utf-8"))   # what Postgres runs on first volume creation
    db.ensure_schema(conn)                               # what the app runs at every start
    yield conn
    conn.close()

@pytest.fixture
def conn(schema_conn):
    """Empty tables for every test: autocommit is on, so a rollback can't undo writes"""
    schema_conn.execute("TRUNCATE articles, runs, digests RESTART IDENTITY")
    return schema_conn

# --------------------------------------------------------------------------- helpers
def url(n: int) -> str:
    return f"https://example.com/{n}"

def make_row(n: int, hours_old: float = 1, **kw) -> dict:
    row = {
        "source": "Wire",
        "category": "geopolitics",
        "url": url(n),
        "title": f"Title {n}",
        "summary": f"Summary {n}",
        "lang": "en",
        "published_at": datetime.now(timezone.utc) - timedelta(hours=hours_old),
    }
    row.update(kw)
    return row

def id_for(conn, n: int) -> int:
    return conn.execute("SELECT id FROM articles WHERE url = %s", (url(n),)).fetchone()["id"]

def urls(rows: list[dict]) -> set[str]:
    return {r["url"] for r in rows}

def count(conn) -> int:
    return conn.execute("SELECT count(*) AS n FROM articles").fetchone()["n"]

# Both fetch functions share the same unsent + time-window filter, so most tests run on both
FETCHERS = [
    pytest.param(lambda c, **kw: db.fetch_unsent(c, per_category=10, **kw), id="fetch_unsent"),
    pytest.param(db.fetch_all_unsent, id="fetch_all_unsent"),
]

# --------------------------------------------------------------------------- dedup on url
def test_insert_article_dedups_on_url(conn):
    assert db.insert_article(conn, make_row(1)) is True
    assert db.insert_article(conn, make_row(1, title="Changed title")) is False
    rows = conn.execute("SELECT title FROM articles").fetchall()
    assert rows == [{"title": "Title 1"}]          # first version kept, not overwritten

def test_same_url_from_other_source_is_still_a_duplicate(conn):
    db.insert_article(conn, make_row(1))
    assert db.insert_article(conn, make_row(1, source="Other", category="tech")) is False
    assert count(conn) == 1

# --------------------------------------------------------------------------- 24-hour window
@pytest.mark.parametrize("fetch", FETCHERS)
def test_window_keeps_last_24h_only(conn, fetch):
    # 23h / 25h, not exactly 24h: now() moves between insert and select, so the boundary is flaky
    db.insert_article(conn, make_row(1, hours_old=23))
    db.insert_article(conn, make_row(2, hours_old=25))
    assert urls(fetch(conn)) == {url(1)}


@pytest.mark.parametrize("fetch", FETCHERS)
def test_window_respects_custom_hours(conn, fetch):
    db.insert_article(conn, make_row(1, hours_old=5))
    db.insert_article(conn, make_row(2, hours_old=1))
    assert urls(fetch(conn, hours=3)) == {url(2)}


def test_fetch_unsent_caps_per_category_newest_first(conn):
    for n, hours_old in [(1, 1), (2, 2), (3, 3)]:
        db.insert_article(conn, make_row(n, hours_old=hours_old))
    db.insert_article(conn, make_row(4, hours_old=1, category="tech"))
    rows = db.fetch_unsent(conn, per_category=2)
    assert [r["url"] for r in rows] == [url(1), url(2), url(4)]   # ordered by category, then newest

# --------------------------------------------------------------------------- fetch_recent_stories
def section(category: str, *titles: str, mode: str = "summary") -> dict:
    """A payload section shaped like build_summary_digest writes it"""
    if mode == "summary":
        stories = [{"title": t, "summary": f"{t} summary"} for t in titles]
    else:
        stories = [{"title": t, "sources": []} for t in titles]    # headlines mode: no summary key
    return {"category": category, "label": category, "mode": mode, "stories": stories}


def save(conn, *sections: dict, kind: str = "summary", hours_ago: float = 0) -> None:
    digest_id = db.save_digest(conn, kind, "Subject", {"sections": list(sections)}, None, 0, 0, [])
    if hours_ago:   # save_digest always stamps now(): move it back in time for window tests
        conn.execute("UPDATE digests SET created_at = now() - make_interval(hours => %s) WHERE id = %s",
                     (hours_ago, digest_id))


def test_fetch_recent_stories_groups_by_category_newest_first(conn):
    save(conn, section("tech", "Old tech"), hours_ago=5)
    save(conn, section("tech", "New tech", "Other tech"), section("economy", "Rates"))
    assert db.fetch_recent_stories(conn) == {
        "tech": [{"title": "New tech", "summary": "New tech summary"},
                 {"title": "Other tech", "summary": "Other tech summary"},
                 {"title": "Old tech", "summary": "Old tech summary"}],
        "economy": [{"title": "Rates", "summary": "Rates summary"}],
    }


def test_fetch_recent_stories_respects_window(conn):
    # 47h / 49h around the 48h default, same reason as the article window tests
    save(conn, section("tech", "Recent"), hours_ago=47)
    save(conn, section("tech", "Too old"), hours_ago=49)
    assert db.fetch_recent_stories(conn) == {"tech": [{"title": "Recent", "summary": "Recent summary"}]}
    assert db.fetch_recent_stories(conn, hours=24) == {}


def test_fetch_recent_stories_keeps_headline_sections_without_summary(conn):
    save(conn, section("tech", "Just a headline", mode="headlines"))
    assert db.fetch_recent_stories(conn) == {"tech": [{"title": "Just a headline", "summary": None}]}


def test_fetch_recent_stories_ignores_other_kinds(conn):
    assert db.fetch_recent_stories(conn) == {}
    save(conn, section("tech", "Raw"), kind="headlines")
    assert db.fetch_recent_stories(conn) == {}


def test_fetch_recent_stories_includes_the_lead(conn):
    payload = {"lead": {"category": "geo", "title": "Top", "summary": "Top summary"},
               "sections": [section("geo", "Other")]}
    db.save_digest(conn, "summary", "Subject", payload, None, 0, 0, [])
    assert db.fetch_recent_stories(conn) == {"geo": [{"title": "Top", "summary": "Top summary"},
                                                     {"title": "Other", "summary": "Other summary"}]}


def test_fetch_recent_curiosities_newest_first_within_window(conn):
    for title, days in [("Old", 20), ("Mid", 3), ("New", 0)]:
        digest_id = db.save_digest(conn, "summary", "S", {"sections": [], "curiosity": {"title": title}},
                                   None, 0, 0, [])
        conn.execute("UPDATE digests SET created_at = now() - make_interval(days => %s) WHERE id = %s",
                     (days, digest_id))
    db.save_digest(conn, "summary", "S", {"sections": []}, None, 0, 0, [])     # no curiosity: ignored
    assert db.fetch_recent_curiosities(conn) == ["New", "Mid"]

# --------------------------------------------------------------------------- mark_sent
@pytest.mark.parametrize("fetch", FETCHERS)
def test_mark_sent_hides_only_marked_articles(conn, fetch):
    for n in (1, 2, 3):
        db.insert_article(conn, make_row(n))
    db.mark_sent(conn, [id_for(conn, 1), id_for(conn, 2)])
    assert urls(fetch(conn)) == {url(3)}
    sent = conn.execute("SELECT count(*) AS n FROM articles WHERE sent_at IS NOT NULL").fetchone()["n"]
    assert sent == 2


def test_mark_sent_empty_list_is_a_noop(conn):
    db.insert_article(conn, make_row(1))
    db.mark_sent(conn, [])
    assert urls(db.fetch_all_unsent(conn)) == {url(1)}

# --------------------------------------------------------------------------- ensure_schema
def test_ensure_schema_is_idempotent(conn):
    # The session fixture already ran it once; these are runs two and three, on a table with data
    db.insert_article(conn, make_row(1))
    article_id = id_for(conn, 1)
    db.save_lead(conn, article_id, "Lead text", "ok")

    db.ensure_schema(conn)
    db.ensure_schema(conn)

    row = conn.execute("SELECT lead, lead_status FROM articles WHERE id = %s", (article_id,)).fetchone()
    assert row == {"lead": "Lead text", "lead_status": "ok"}     # upgrade didn't wipe existing data
    assert db.save_digest(conn, "summary", "Subject", {"stories": []}, None, 0, 0, []) == 1   # digests usable