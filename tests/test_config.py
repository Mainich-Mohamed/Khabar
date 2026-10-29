import pytest

from app.config import _hours, get_settings, load_sources

ENV_KEYS = ["DATABASE_URL", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO",
            "SOURCES_PATH", "MAX_PER_CATEGORY", "TIMEZONE", "DIGEST_LANGUAGE", "DIGEST_HOURS",
            "DIGEST_VOICE", "MAX_STORIES_PER_CATEGORY", "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_MAX_INPUT",
            "GEMINI_LEAD_CHARS", "GEMINI_INTERVAL", "UPDATE_LOOKBACK_HOURS"]


@pytest.fixture
def clean_env(monkeypatch):
    # app.config already ran load_dotenv() at import: drop whatever .env put in the environment
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


# --------------------------------------------------------------------------- _hours
def test_hours_sorted_and_deduplicated():
    assert _hours("22, 7,16,7") == [7, 16, 22]


def test_hours_ignores_empty_items():
    assert _hours("7,,16,") == [7, 16]


@pytest.mark.parametrize("raw", ["", " , ", "24", "-1", "7,25"])
def test_hours_rejects_invalid(raw):
    with pytest.raises(ValueError):
        _hours(raw)


def test_hours_rejects_non_numbers():
    with pytest.raises(ValueError):
        _hours("seven")


# --------------------------------------------------------------------------- get_settings
def test_settings_defaults(clean_env):
    s = get_settings()
    assert s.smtp_port == 587
    assert s.digest_hours == [7, 16, 22]
    assert s.timezone == "Africa/Casablanca"
    assert s.email_to == []
    assert s.gemini_api_key == ""
    assert s.gemini_interval == 7.0
    assert s.update_lookback_hours == 48
    assert s.max_stories_per_category == 4
    assert s.digest_voice == "lively"


def test_settings_voice_plain_and_invalid(clean_env):
    clean_env.setenv("DIGEST_VOICE", "plain")
    assert get_settings().digest_voice == "plain"
    clean_env.setenv("DIGEST_VOICE", "loud")
    with pytest.raises(ValueError, match="DIGEST_VOICE"):
        get_settings()


def test_settings_parses_env(clean_env):
    clean_env.setenv("SMTP_PASSWORD", "abcd efgh ijkl mnop")   # Gmail shows app passwords with spaces
    clean_env.setenv("EMAIL_TO", " a@x.com, ,b@y.com ")
    clean_env.setenv("DIGEST_HOURS", "8,20")
    clean_env.setenv("GEMINI_INTERVAL", "2.5")
    clean_env.setenv("MAX_STORIES_PER_CATEGORY", "4")
    clean_env.setenv("UPDATE_LOOKBACK_HOURS", "24")
    s = get_settings()
    assert s.smtp_password == "abcdefghijklmnop"
    assert s.email_to == ["a@x.com", "b@y.com"]
    assert s.digest_hours == [8, 20]
    assert s.gemini_interval == 2.5
    assert s.max_stories_per_category == 4
    assert s.update_lookback_hours == 24


@pytest.mark.parametrize("key, attr, default", [
    ("SMTP_PORT", "smtp_port", 587),
    ("TIMEZONE", "timezone", "Africa/Casablanca"),
    ("DIGEST_HOURS", "digest_hours", [7, 16, 22]),
])
def test_settings_whitespace_env_value_uses_default(clean_env, key, attr, default):
    clean_env.setenv(key, "   ")
    assert getattr(get_settings(), attr) == default


# --------------------------------------------------------------------------- load_sources
def _write(tmp_path, text: str) -> str:
    p = tmp_path / "sources.yaml"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_load_sources(tmp_path):
    path = _write(tmp_path, """
categories:
  tech: "Tech"
  world: "World"
sources:
  - {name: A, category: tech, url: "https://a/rss", weight: 0.9}
  - {name: B, category: world, url: "https://b/rss", lang: fr}
""")
    cfg = load_sources(path)
    assert list(cfg.categories) == ["tech", "world"]           # order kept: it is the digest order
    assert cfg.sources[1].lang == "fr"
    assert cfg.weight("A") == 0.9
    assert cfg.weight("B") == 0.5                              # default weight
    assert cfg.weight("Removed source") == 0.5


def test_load_sources_rejects_undeclared_category(tmp_path):
    path = _write(tmp_path, """
categories: {tech: "Tech"}
sources:
  - {name: A, category: sports, url: "https://a/rss"}
""")
    with pytest.raises(ValueError, match="sports"):
        load_sources(path)


def test_load_sources_rejects_unknown_field(tmp_path):
    path = _write(tmp_path, """
categories: {tech: "Tech"}
sources:
  - {name: A, category: tech, url: "https://a/rss", wieght: 1}
""")
    with pytest.raises(TypeError):
        load_sources(path)


def test_shipped_sources_yaml_is_valid():
    cfg = load_sources("config/sources.yaml")
    assert cfg.sources
    names = [s.name for s in cfg.sources]
    assert len(names) == len(set(names)), "duplicate source names make weight() ambiguous"
    for s in cfg.sources:
        assert s.url.startswith("https://"), s.name
        assert 0 < s.weight <= 1, s.name
        assert s.lang in {"en", "fr", "ar"}, s.name