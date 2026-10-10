-- Runs only the first time the Postgres volume is created.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS articles (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT        NOT NULL,
    category      TEXT        NOT NULL,
    url           TEXT        NOT NULL UNIQUE,
    title         TEXT        NOT NULL,
    summary       TEXT,
    lang          TEXT,
    published_at  TIMESTAMPTZ NOT NULL,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at       TIMESTAMPTZ,
    embedding     vector(384)          -- filled in Step 3 (clustering)
);

CREATE INDEX IF NOT EXISTS idx_articles_cat_pub ON articles (category, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_unsent  ON articles (published_at DESC) WHERE sent_at IS NULL;

CREATE TABLE IF NOT EXISTS runs (
    id            BIGSERIAL PRIMARY KEY,
    kind          TEXT        NOT NULL,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    new_articles  INT         DEFAULT 0,
    sent_articles INT         DEFAULT 0,
    errors        TEXT
);
