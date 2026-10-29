"""Shared fixtures. Unit tests only: no network, no database, no real SMTP."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.config import Settings, Source, SourcesConfig

NOW = datetime.now(timezone.utc)


def make_article(id_: int, source: str = "Wire", hours_old: float = 1, **kw) -> dict:
    a = {
        "id": id_,
        "source": source,
        "category": "geopolitics",
        "url": f"https://example.com/{id_}",
        "title": f"Title {id_}",
        "summary": f"Summary {id_}",
        "lead": None,
        "lead_status": None,
        "published_at": NOW - timedelta(hours=hours_old),
    }
    a.update(kw)
    return a


@pytest.fixture
def article():
    return make_article


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="postgresql://x", smtp_host="smtp.test", smtp_port=587,
        smtp_user="me@test", smtp_password="pw", email_to=["me@test"],
        sources_path="config/sources.yaml", max_per_category=3, timezone="Africa/Casablanca",
        digest_language="English", digest_hours=[7, 16, 22], digest_voice="lively", max_stories_per_category=6,
        gemini_api_key="key", gemini_model="gemini-test", gemini_max_input=25,
        gemini_lead_chars=900, gemini_interval=0, update_lookback_hours=48,
    )


@pytest.fixture
def sources_cfg() -> SourcesConfig:
    return SourcesConfig(
        categories={"geopolitics": "Geopolitics", "tech": "Tech & AI"},
        sources=[
            Source(name="Trusted", url="https://t/rss", category="geopolitics", weight=1.0),
            Source(name="Meh", url="https://m/rss", category="geopolitics", weight=0.2),
            Source(name="Techy", url="https://x/rss", category="tech", weight=0.9),
        ],
    )


@pytest.fixture
def mock_client():
    """Build an httpx.Client whose requests are answered by `handler(request)`."""
    def make(handler) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    return make


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Retry/backoff code must never actually sleep during tests."""
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
