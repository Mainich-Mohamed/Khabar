import os
from dataclasses import dataclass

import yaml
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    email_to: list[str]
    sources_path: str
    max_per_category: int          # headlines mode / fallback
    timezone: str
    digest_language: str
    digest_hours: list[int]
    max_stories_per_category: int
    gemini_api_key: str
    gemini_model: str
    gemini_max_input: int          # articles sent per category
    gemini_lead_chars: int
    gemini_interval: float         # seconds between calls (free tier per-minute limit)
    update_lookback_hours: int     # sent stories this recent are compared with new ones (updates/repeats)


def _hours(raw: str) -> list[int]:
    hours = sorted({int(h) for h in raw.split(",") if h.strip()})
    if not hours or any(not 0 <= h <= 23 for h in hours):
        raise ValueError(f"DIGEST_HOURS must be comma-separated hours 0-23, got {raw!r}")
    return hours


def get_settings() -> Settings:
    env = lambda k, d="": (os.environ.get(k) or "").strip() or d
    return Settings(
        database_url=env("DATABASE_URL", "postgresql://news:news@localhost:5433/news"),
        smtp_host=env("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(env("SMTP_PORT", "587")),
        smtp_user=env("SMTP_USER"),
        smtp_password=env("SMTP_PASSWORD").replace(" ", ""),
        email_to=[e.strip() for e in env("EMAIL_TO").split(",") if e.strip()],
        sources_path=env("SOURCES_PATH", "config/sources.yaml"),
        max_per_category=int(env("MAX_PER_CATEGORY", "8")),
        timezone=env("TIMEZONE", "Africa/Casablanca"),
        digest_language=env("DIGEST_LANGUAGE", "English"),
        digest_hours=_hours(env("DIGEST_HOURS", "7,16,22")),
        max_stories_per_category=int(env("MAX_STORIES_PER_CATEGORY", "6")),
        gemini_api_key=env("GEMINI_API_KEY"),
        gemini_model=env("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        gemini_max_input=int(env("GEMINI_MAX_INPUT", "25")),
        gemini_lead_chars=int(env("GEMINI_LEAD_CHARS", "900")),
        gemini_interval=float(env("GEMINI_INTERVAL", "7")),
        update_lookback_hours=int(env("UPDATE_LOOKBACK_HOURS", "48")),
    )


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    category: str
    lang: str = "en"
    weight: float = 0.5


@dataclass(frozen=True)
class SourcesConfig:
    categories: dict[str, str]   # key -> display label, in digest order
    sources: list[Source]

    def weight(self, source_name: str) -> float:
        for s in self.sources:
            if s.name == source_name:
                return s.weight
        return 0.5  # source removed from config since the article was stored


def load_sources(path: str) -> SourcesConfig:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    categories = dict(raw["categories"])
    sources = [Source(**s) for s in raw["sources"]]
    unknown = {s.category for s in sources} - categories.keys()
    if unknown:
        raise ValueError(f"sources.yaml uses undeclared categories: {unknown}")
    return SourcesConfig(categories=categories, sources=sources)