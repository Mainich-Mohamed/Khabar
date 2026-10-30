from types import SimpleNamespace

import pytest

from app import pipeline
from app.digest import Section
from app.llm import Curiosity, LLMError, QuotaExhausted, Story, Usage
from app.pipeline import Prepared, front_page, rank, run_digest, summarize_sections


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
    lead = 0          # index returned by pick_lead, or an exception to raise
    curio = None      # an exception to raise from curiosity()

    def __init__(self, behaviour: dict):
        self.behaviour, self.calls, self.previous = behaviour, [], {}

    def summarize(self, label, arts, previous=None):
        self.calls.append(label)
        self.previous[label] = previous
        result = self.behaviour[label]
        if isinstance(result, Exception):
            raise result
        if isinstance(result, list):      # explicit stories, e.g. with statuses
            return result, Usage(10, 2)
        return [Story(title=f"{label} story", summary="s", sources=[], single_source=True)], Usage(10, 2)

    def pick_lead(self, candidates):
        self.calls.append("lead")
        if isinstance(self.lead, Exception):
            raise self.lead
        return self.lead, "why", Usage(1, 1)

    highs = None      # stories returned by highlights(), or an exception to raise

    def highlights(self, articles, previous=None, max_stories=5):
        self.calls.append("highlights")
        if isinstance(self.highs, Exception):
            raise self.highs
        return self.highs, Usage(10, 2)

    def curiosity(self, previous):
        self.calls.append("curiosity")
        if isinstance(self.curio, Exception):
            raise self.curio
        return Curiosity("Fact", "Text", "Topic"), Usage(1, 1)


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


def status_story(title, status="new", previous_title=None) -> Story:
    return Story(title=title, summary="s", sources=[], single_source=True,
                 status=status, previous_title=previous_title)


def test_summarize_sections_passes_each_category_its_history(sources_cfg, article, settings):
    z = FakeSummarizer({"Geopolitics": None, "Tech & AI": None})
    p = prepared(sources_cfg, article)
    p.previous = {"geopolitics": [{"title": "Old geo", "summary": None}]}
    summarize_sections(z, p, settings, [])
    assert z.previous == {"Geopolitics": [{"title": "Old geo", "summary": None}], "Tech & AI": None}


def test_summarize_sections_moves_repeats_to_dropped(sources_cfg, article, settings):
    z = FakeSummarizer({"Geopolitics": [status_story("New"), status_story("Upd", "update", "Old"),
                                        status_story("Rep", "repeat", "Older")],
                        "Tech & AI": [status_story("Only rep", "repeat", "Old tech")]})
    sections, _, fallbacks = summarize_sections(z, prepared(sources_cfg, article), settings, [])
    geo, tech = sections
    assert [s.title for s in geo.stories] == ["New", "Upd"]
    assert [s.title for s in geo.dropped] == ["Rep"]
    assert tech.stories == [] and [s.title for s in tech.dropped] == ["Only rep"]
    assert not tech.is_fallback and fallbacks == []      # all repeats is not an LLM failure


# --------------------------------------------------------------------------- front_page
def two_sections():
    return [Section("geopolitics", "Geopolitics", stories=[status_story("G1"), status_story("G2")]),
            Section("tech", "Tech & AI", stories=[status_story("T1")])]


def test_front_page_moves_the_lead_out_of_its_section():
    z = FakeSummarizer({})
    z.lead = 2                                  # third candidate: the tech story
    secs, errors = two_sections(), []
    lead, curio, usage = front_page(z, secs, ["Old fact"], errors)
    assert (lead.story.title, lead.key, lead.why_it_matters) == ("T1", "tech", "why")
    assert secs[1].stories == [] and [s.title for s in secs[0].stories] == ["G1", "G2"]
    assert curio.title == "Fact" and errors == [] and usage.input_tokens == 2


def test_front_page_lead_failure_still_gets_curiosity():
    z = FakeSummarizer({})
    z.lead = LLMError("bad answer")
    secs, errors = two_sections(), []
    lead, curio, _ = front_page(z, secs, [], errors)
    assert lead is None and curio is not None
    assert [s.title for s in secs[0].stories] == ["G1", "G2"]    # nothing removed
    assert errors == ["top story: bad answer"]


def test_front_page_quota_skips_the_curiosity():
    z = FakeSummarizer({})
    z.lead = QuotaExhausted("daily quota")
    lead, curio, _ = front_page(z, two_sections(), [], [])
    assert (lead, curio) == (None, None) and "curiosity" not in z.calls


def test_front_page_curiosity_failure_is_recorded():
    z = FakeSummarizer({})
    z.curio = LLMError("incomplete")
    errors = []
    lead, curio, _ = front_page(z, two_sections(), [], errors)
    assert lead is not None and curio is None
    assert errors == ["curiosity: incomplete"]


def test_front_page_without_stories_skips_the_lead(article):
    z = FakeSummarizer({})
    lead, curio, _ = front_page(z, [Section("tech", "Tech", headlines=[article(1)])], [], [])
    assert lead is None and curio is not None and z.calls == ["curiosity"]


def test_front_page_without_summarizer():
    lead, curio, usage = front_page(None, two_sections(), [], [])
    assert (lead, curio, usage.input_tokens) == (None, None, 0)


# --------------------------------------------------------------------------- prepare (sources/ingest/DB faked)
def test_prepare_loads_history_with_lookback(monkeypatch, sources_cfg, article, settings):
    seen = {}

    def fetch_recent_stories(conn, hours):
        seen["hours"] = hours
        return {"tech": [{"title": "Old", "summary": None}]}

    monkeypatch.setattr(pipeline, "load_sources", lambda path: sources_cfg)
    monkeypatch.setattr(pipeline, "ingest_all", lambda conn, sources, insert: (0, []))
    monkeypatch.setattr(pipeline, "extract_leads", lambda conn, arts, save: None)
    monkeypatch.setattr(pipeline, "db", SimpleNamespace(
        insert_article=None, save_lead=None, fetch_recent_stories=fetch_recent_stories,
        fetch_recent_curiosities=lambda conn: ["Old fact"],
        fetch_all_unsent=lambda conn: [article(1, category="tech")]))
    p = pipeline.prepare(None, settings, cap=5)
    assert seen["hours"] == 48
    assert p.previous == {"tech": [{"title": "Old", "summary": None}]}
    assert p.curiosities == ["Old fact"]


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


def test_run_digest_uses_a_fresh_connection_for_the_writes(wired):
    connects = []
    wired.db.connect = lambda url: connects.append(url) or FakeConn()
    run_digest(wired.settings, send=True)
    assert len(connects) == 2          # one for prepare, one for send + writes


def test_run_digest_fails_before_sending_when_reconnect_fails(wired):
    attempts = []

    def connect(url):
        attempts.append(url)
        if len(attempts) == 2:
            raise RuntimeError("neon down")
        return FakeConn()

    wired.db.connect = connect
    with pytest.raises(RuntimeError):
        run_digest(wired.settings, send=True)
    assert wired.sent == []            # no email if the DB is unreachable


def test_run_digest_preview_sends_and_marks_nothing(wired):
    r = run_digest(wired.settings, send=False)
    assert wired.sent == []
    assert "mark_sent" not in wired.db.calls and "save_digest" not in wired.db.calls
    assert "finish_run" in wired.db.calls
    assert "Geopolitics story" in r.digest.html


# --------------------------------------------------------------------------- run_update
def hl(title, ids, status="new") -> Story:
    return Story(title=title, summary="s", sources=[{"name": "BBC", "url": "https://b/1"}],
                 single_source=True, article_ids=ids, status=status)


@pytest.fixture
def updating(wired, monkeypatch):
    marked = []
    wired.db.mark_sent = lambda conn, ids: marked.append(ids)
    z = FakeSummarizer({})
    monkeypatch.setattr(pipeline, "make_summarizer", lambda s: z)
    return SimpleNamespace(wired=wired, z=z, marked=marked)


def test_run_update_sends_and_marks_only_shown_articles(updating):
    updating.z.highs = [hl("A", [1]), hl("B", [2]), hl("Same again", [3], "repeat")]
    r = pipeline.run_update(updating.wired.settings, send=True)
    assert len(updating.wired.sent) == 1 and updating.wired.sent[0][0] == r.digest.subject
    assert updating.marked == [[1, 2]]                 # the repeat's article stays unsent for the evening
    assert updating.wired.db.calls[-2:] == ["save_digest", "finish_run"]


def test_run_update_too_few_stories_sends_nothing(updating):
    updating.z.highs = [hl("Only one", [1]), hl("Repeat", [2], "repeat")]
    r = pipeline.run_update(updating.wired.settings, send=True)
    assert r.digest is None and updating.wired.sent == [] and updating.marked == []
    assert "save_digest" not in updating.wired.db.calls and "finish_run" in updating.wired.db.calls


def test_run_update_uses_the_article_category_as_label(updating, monkeypatch, sources_cfg, article):
    tech = [article(1, category="tech"), article(2, category="geopolitics")]
    monkeypatch.setattr(pipeline, "prepare", lambda conn, s, cap: Prepared(
        sources_cfg, tech, {"tech": tech[:1], "geopolitics": tech[1:]}, new_articles=2, errors=[]))
    updating.z.highs = [hl("A", [1]), hl("B", [2])]
    r = pipeline.run_update(updating.wired.settings, send=False)
    assert "TECH &amp; AI" in r.digest.html and "GEOPOLITICS" in r.digest.html


def test_run_update_llm_failure_fails_the_run(updating):
    updating.z.highs = LLMError("boom")
    with pytest.raises(LLMError):
        pipeline.run_update(updating.wired.settings, send=True)
    assert updating.wired.sent == [] and updating.marked == []


def test_run_update_without_articles_skips_the_llm(updating, monkeypatch, sources_cfg):
    monkeypatch.setattr(pipeline, "prepare", lambda conn, s, cap: Prepared(sources_cfg, [], {}, 0, []))
    r = pipeline.run_update(updating.wired.settings, send=True)
    assert r.digest is None and updating.z.calls == []


def test_run_update_preview_sends_and_marks_nothing(updating):
    updating.z.highs = [hl("A", [1]), hl("B", [2])]
    r = pipeline.run_update(updating.wired.settings, send=False)
    assert r.digest is not None and updating.wired.sent == [] and updating.marked == []
