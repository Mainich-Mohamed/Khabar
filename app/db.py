import json

import psycopg
from psycopg.rows import dict_row

# Idempotent schema upgrades, applied at every start. init.sql only runs when the
# Postgres volume is first created, so new columns/tables must be added here
SCHEMA_UPGRADES = [
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS lead TEXT",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS lead_status TEXT",  # ok | failed | skipped
    """
    CREATE TABLE IF NOT EXISTS digests (
        id            BIGSERIAL PRIMARY KEY,
        kind          TEXT        NOT NULL,          -- summary | headlines
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        subject       TEXT        NOT NULL,
        payload       JSONB       NOT NULL,          -- structured stories: feeds the email now, the app later
        model         TEXT,
        input_tokens  INT         DEFAULT 0,
        output_tokens INT         DEFAULT 0,
        fallback_categories TEXT[] DEFAULT '{}'      -- categories that fell back to headlines
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_digests_created ON digests (created_at DESC)",
]


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url, autocommit=True, row_factory=dict_row)


def ensure_schema(conn: psycopg.Connection) -> None:
    for stmt in SCHEMA_UPGRADES:
        conn.execute(stmt)


def insert_article(conn: psycopg.Connection, a: dict) -> bool:
    """Insert an article; returns True if it was new (URL not seen before)"""
    row = conn.execute(
        """
        INSERT INTO articles (source, category, url, title, summary, lang, published_at)
        VALUES (%(source)s, %(category)s, %(url)s, %(title)s, %(summary)s, %(lang)s, %(published_at)s)
        ON CONFLICT (url) DO NOTHING
        RETURNING id
        """,
        a,
    ).fetchone()
    return row is not None


def fetch_unsent(conn: psycopg.Connection, per_category: int, hours: int = 24) -> list[dict]:
    """Newest unsent articles from the last `hours`, capped per category (headlines mode)"""
    return conn.execute(
        """
        SELECT id, source, category, url, title, summary, lead, published_at FROM (
            SELECT *, row_number() OVER (PARTITION BY category ORDER BY published_at DESC) AS rn
            FROM articles
            WHERE sent_at IS NULL AND published_at > now() - make_interval(hours => %s)
        ) t
        WHERE rn <= %s
        ORDER BY category, published_at DESC
        """,
        (hours, per_category),
    ).fetchall()


def fetch_all_unsent(conn: psycopg.Connection, hours: int = 24) -> list[dict]:
    """Every unsent article in the window; ranking happens in Python (needs source weights)"""
    return conn.execute(
        """
        SELECT id, source, category, url, title, summary, lead, lead_status, published_at
        FROM articles
        WHERE sent_at IS NULL AND published_at > now() - make_interval(hours => %s)
        ORDER BY published_at DESC
        """,
        (hours,),
    ).fetchall()

def fetch_recent_stories(conn: psycopg.Connection, hours: int = 48) -> dict[str, list[dict]]:
    """Stories emailed in the last `hours`, grouped by category, newest digest first (update detection)"""
    rows = conn.execute(
        """
        SELECT payload FROM digests
        WHERE kind IN ('summary', 'update') AND created_at > now() - make_interval(hours => %s)
        ORDER BY created_at DESC
        """,
        (hours,),
    ).fetchall()
    by_cat: dict[str, list[dict]] = {}
    for row in rows:
        lead = row["payload"].get("lead")
        if lead:   # the top story is stored outside its section
            by_cat.setdefault(lead["category"], []).append(
                {"title": lead["title"], "summary": lead.get("summary")})
        for sec in row["payload"].get("sections", []):
            for st in sec.get("stories", []):
                by_cat.setdefault(sec["category"], []).append(
                    {"title": st["title"], "summary": st.get("summary")})
    return by_cat


def fetch_recent_curiosities(conn: psycopg.Connection, days: int = 14) -> list[str]:
    """Titles of recent "Did you know?" items, newest first, so the model doesn't repeat itself"""
    rows = conn.execute(
        """
        SELECT payload->'curiosity'->>'title' AS title FROM digests
        WHERE kind = 'summary' AND created_at > now() - make_interval(days => %s)
        ORDER BY created_at DESC
        """,
        (days,),
    ).fetchall()
    return [r["title"] for r in rows if r["title"]]


def save_lead(conn: psycopg.Connection, article_id: int, lead: str | None, status: str) -> None:
    conn.execute("UPDATE articles SET lead = %s, lead_status = %s WHERE id = %s", (lead, status, article_id))


def mark_sent(conn: psycopg.Connection, ids: list[int]) -> None:
    if ids:
        conn.execute("UPDATE articles SET sent_at = now() WHERE id = ANY(%s)", (ids,))


def save_digest(conn, kind: str, subject: str, payload: dict, model: str | None,
                input_tokens: int, output_tokens: int, fallback_categories: list[str]) -> int:
    return conn.execute(
        """
        INSERT INTO digests (kind, subject, payload, model, input_tokens, output_tokens, fallback_categories)
        VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s) RETURNING id
        """,
        (kind, subject, json.dumps(payload, default=str), model, input_tokens, output_tokens, fallback_categories),
    ).fetchone()["id"]


def start_run(conn: psycopg.Connection, kind: str) -> int:
    return conn.execute("INSERT INTO runs (kind) VALUES (%s) RETURNING id", (kind,)).fetchone()["id"]


def finish_run(conn: psycopg.Connection, run_id: int, new: int, sent: int, errors: list[str]) -> None:
    conn.execute(
        "UPDATE runs SET finished_at = now(), new_articles = %s, sent_articles = %s, errors = %s WHERE id = %s",
        (new, sent, "\n".join(errors) or None, run_id),
    )
