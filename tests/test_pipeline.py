from types import SimpleNamespace

import pytest

from app import pipeline
from app.llm import LLMError, QuotaExhausted, Story, Usage
from app.pipeline import Prepared, rank, run_digest, summarize_sections


# --------------------------------------------------------------------------- rank
def test_rank_prefers_trusted_sources(sources_cfg, article):
    trusted, meh = article(1, source="Trusted", hours_old=2), article(2, source="Meh", hours_old=2)
    assert [a["id"] for a in rank([meh, trusted], sources_cfg)] == [1, 2]


def test_rank_prefers_recent(sources_cfg, article):
    old, new = article(1, source="Trusted", hours_old=30), article(2, source="Trusted", hours_old=1)
    assert [a["id"] for a in rank([old, new], sources_cfg)] == [2, 1]


def test_rank_recency_can_beat_weight(sources_cfg, article):
    # score = weight / (1 + hours_old / 12)
    stale_trusted = article(1, source="Trusted", hours_old=60)    # 1/6 ~ 0.167
    fresh_meh = article(2, source="Meh", hours_old=0)             # 0.2
    assert rank([stale_trusted, fresh_meh], sources_cfg)[0]["id"] == 2


def test_rank_unknown_source_uses_default_weight(sources_cfg, article):
    gone, meh = article(1, source="Removed", hours_old=1), article(2, source="Meh", hours_old=1)
    assert rank([meh, gone], sources_cfg)[0]["id"] == 1         # 0.5 > 0.2


# --------------------------------------------------------------------------- summarize_sections
class FakeSummarizer:
    max_input = 25
    label = "fake"

    def __init__(self, behaviour: dict):
        self.behaviour, self.calls = behaviour, []

    def summarize(self, label, arts):
        self.calls.append(label)
        result = self.behaviour[label]
        if isinstance(result, Exception):
            raise result
        return [Story(title=f"{label} story", summary="s", sources=[], single_source=True)], Usage(10, 2)


def prepared(sources_cfg, article, cats=("geopolitics", "tech")) -> Prepared:
    candidates = {c: [article(i, category=c) for i in range(1, 6)] for c in cats}
    return Prepared(cfg=sources_cfg, unsent=[], candidates=candidates, new_articles=0, errors=[])


def test_summarize_sections_happy_path(sources_cfg, article, settings):
    z = FakeSummarizer({"Geopolitics": None, "Tech & AI": None})
    errors = []
    sections, usage, fallbacks = summarize_sections(z, prepared(sources_cfg, article), settings, errors)
    assert [s.key for s in sections] == ["geopolitics", "tech"]        # category order from config
    assert all(not s.is_fallback for s in sections)
    assert (usage.input_tokens, usage.output_tokens) == (20, 4)
    assert fallbacks == [] and errors == []


def test_summarize_sections_skips_empty_categories(sources_cfg, article, settings):
    z = FakeSummarizer({"Tech & AI": None})
    sections, _, _ = summarize_sections(z, prepared(sources_cfg, article, cats=("tech",)), settings, [])
    assert [s.key for s in sections] == ["tech"]
    assert z.calls == ["Tech & AI"]


def test_summarize_sections_failure_falls_back_to_headlines(sources_cfg, article, settings):
    z = FakeSummarizer({"Geopolitics": LLMError("bad json"), "Tech & AI": None})
    errors = []
    sections, _, fallbacks = summarize_sections(z, prepared(sources_cfg, article), settings, errors)
    geo, tech = sections
    assert geo.is_fallback and len(geo.headlines) == settings.max_per_category
    assert not tech.is_fallback
    assert fallbacks == ["geopolitics"]
    assert errors == ["summarize geopolitics: bad json"]


def test_summarize_sections_quota_exhausted_stops_calling(sources_cfg, article, settings):
    z = FakeSummarizer({"Geopolitics": QuotaExhausted("daily quota"), "Tech & AI": None})
    errors = []
    sections, _, fallbacks = summarize_sections(z, prepared(sources_cfg, article), settings, errors)
    assert z.calls == ["Geopolitics"]                  # Tech never attempted
    assert fallbacks == ["geopolitics", "tech"]
    assert all(s.is_fallback for s in sections)
    assert len(errors) == 1                            # the skipped category is not logged as an error


def test_summarize_sections_without_summarizer(sources_cfg, article, settings):
    errors = []
    sections, usage, fallbacks = summarize_sections(None, prepared(sources_cfg, article), settings, errors)
    assert fallbacks == ["geopolitics", "tech"]
    assert errors == [] and usage.input_tokens == 0
    assert all(s.is_fallback for s in sections)


# --------------------------------------------------------------------------- run_digest (DB/email/LLM faked)
class FakeDB:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def fn(*args, **kw):
            self.calls.append(name)
            return {"start_run": 1, "save_digest": 1}.get(name)
        return fn


class FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def wired(monkeypatch, sources_cfg, article, settings):
    fake_db = FakeDB()
    fake_db.connect = lambda url: FakeConn()
    monkeypatch.setattr(pipeline, "db", fake_db)
    unsent = [article(i) for i in range(1, 4)]
    monkeypatch.setattr(pipeline, "prepare", lambda conn, s, cap: Prepared(
        sources_cfg, unsent, {"geopolitics": unsent}, new_articles=3, errors=["Feed X: down"]))
    monkeypatch.setattr(pipeline, "_summarizer_or_none", lambda s: FakeSummarizer({"Geopolitics": None}))
    sent = []
    monkeypatch.setattr(pipeline, "make_emailer", lambda s: SimpleNamespace(send=lambda *a: sent.append(a)))
    return SimpleNamespace(db=fake_db, sent=sent, settings=settings)


def test_run_digest_send(wired):
    r = run_digest(wired.settings, send=True)
    assert len(wired.sent) == 1 and wired.sent[0][0] == r.digest.subject
    assert wired.db.calls[-3:] == ["save_digest", "mark_sent", "finish_run"]
    assert r.considered == 3 and r.new_articles == 3
    assert r.errors == ["Feed X: down"]


def test_run_digest_preview_sends_and_marks_nothing(wired):
    r = run_digest(wired.settings, send=False)
    assert wired.sent == []
    assert "mark_sent" not in wired.db.calls and "save_digest" not in wired.db.calls
    assert "finish_run" in wired.db.calls
    assert "Geopolitics story" in r.digest.html
