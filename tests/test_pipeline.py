from types import SimpleNamespace

import pytest

from app import pipeline
from app.digest import Section
from app.llm import Analysis, Curiosity, LLMError, Overview, Placement, QuotaExhausted, Story, Usage
from app.pipeline import (Prepared, apply_arrangement, arrange_sections, front_page, rank, run_digest,
                          summarize_sections)


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
        return self.lead, Usage(1, 1)

    highs = None      # stories returned by highlights(), or an exception to raise

    def highlights(self, articles, previous=None, max_stories=5):
        self.calls.append("highlights")
        if isinstance(self.highs, Exception):
            raise self.highs
        return self.highs, Usage(10, 2)

    placements = None   # returned by arrange() (None: every story stays), or an exception to raise

    def arrange(self, stories, sections):
        self.calls.append("arrange")
        self.arranged = (stories, sections)
        if isinstance(self.placements, Exception):
            raise self.placements
        if self.placements is None:
            return [Placement(k) for k, _ in stories], Usage(3, 1)
        return self.placements, Usage(3, 1)

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


# --------------------------------------------------------------------------- arrange
LABELS = {"geopolitics": "Geopolitics", "economy": "Economy", "tech": "Tech & AI"}


def sourced(title, *names, ids=()) -> Story:
    return Story(title=title, summary="s", sources=[{"name": n, "url": f"https://{n}/"} for n in names],
                 single_source=len(names) == 1, article_ids=list(ids))


def titles(sections):
    return {sec.key: [st.title for st in sec.stories] for sec in sections}


def test_apply_arrangement_moves_a_story_and_keeps_config_order():
    secs = [Section("geopolitics", "Geopolitics", stories=[sourced("Hack", "BBC"), sourced("War", "AP")]),
            Section("tech", "Tech & AI", stories=[sourced("Phone", "Ars")])]
    out = apply_arrangement(secs, [Placement("tech"), Placement("geopolitics"), Placement("tech")], LABELS)
    assert titles(out) == {"geopolitics": ["War"], "tech": ["Hack", "Phone"]}
    assert [s.key for s in out] == ["geopolitics", "tech"]


def test_apply_arrangement_merges_duplicates_into_the_earlier_story():
    secs = [Section("geopolitics", "Geopolitics", stories=[sourced("Hack", "BBC", ids=[1])]),
            Section("economy", "Economy", stories=[sourced("Exchange robbed", "BBC", "CNBC", ids=[1, 2])])]
    out = apply_arrangement(secs, [Placement("tech"), Placement("economy", same_as=0)], LABELS)
    assert titles(out) == {"geopolitics": [], "economy": [], "tech": ["Hack"]}   # tech created, in config order
    [hack] = out[2].stories
    assert [s["name"] for s in hack.sources] == ["BBC", "CNBC"]                 # no duplicate outlet
    assert hack.article_ids == [1, 2] and hack.single_source is False


def test_apply_arrangement_follows_merge_chains_to_the_first_story():
    secs = [Section("tech", "Tech & AI", stories=[sourced("A", "X"), sourced("B", "Y"), sourced("C", "Z")])]
    out = apply_arrangement(secs, [Placement("tech"), Placement("tech", 0), Placement("tech", 1)], LABELS)
    assert titles(out) == {"tech": ["A"]}
    assert [s["name"] for s in out[0].stories[0].sources] == ["X", "Y", "Z"]


def test_apply_arrangement_never_moves_into_a_headlines_section(article):
    secs = [Section("geopolitics", "Geopolitics", headlines=[article(1)]),
            Section("tech", "Tech & AI", stories=[sourced("Hack", "BBC")])]
    out = apply_arrangement(secs, [Placement("geopolitics")], LABELS)
    assert titles(out) == {"geopolitics": [], "tech": ["Hack"]}
    assert out[0].headlines == [article(1)]


def two_stories():
    return [Section("geopolitics", "Geopolitics", stories=[sourced("Hack", "BBC")]),
            Section("tech", "Tech & AI", stories=[sourced("Phone", "Ars")])]


def test_arrange_sections_sends_described_sections_and_applies_the_answer(sources_cfg):
    z = FakeSummarizer({})
    z.placements = [Placement("tech"), Placement("tech")]
    errors = []
    out, usage = arrange_sections(z, two_stories(), sources_cfg, errors)
    assert titles(out) == {"geopolitics": [], "tech": ["Hack", "Phone"]}
    stories, sections = z.arranged
    assert [k for k, _ in stories] == ["geopolitics", "tech"]
    assert sections == {"geopolitics": "Geopolitics: Geopolitics", "tech": "Tech & AI: Tech & AI"}  # no descriptions
    assert errors == [] and usage.input_tokens == 3


def test_arrange_sections_failure_keeps_sections(sources_cfg):
    z = FakeSummarizer({})
    z.placements = LLMError("no story list")
    errors = []
    out, usage = arrange_sections(z, two_stories(), sources_cfg, errors)
    assert titles(out) == {"geopolitics": ["Hack"], "tech": ["Phone"]}
    assert errors == ["arrange: no story list"] and usage.input_tokens == 0


def test_arrange_sections_skips_the_call_with_fewer_than_two_stories(sources_cfg):
    z = FakeSummarizer({})
    arrange_sections(z, [Section("tech", "Tech & AI", stories=[sourced("Solo", "Ars")])], sources_cfg, [])
    assert z.calls == []
    out, _ = arrange_sections(None, two_stories(), sources_cfg, [])
    assert titles(out) == {"geopolitics": ["Hack"], "tech": ["Phone"]}


# --------------------------------------------------------------------------- front_page
def two_sections():
    return [Section("geopolitics", "Geopolitics", stories=[status_story("G1"), status_story("G2")]),
            Section("tech", "Tech & AI", stories=[status_story("T1")])]


def test_front_page_moves_the_lead_out_of_its_section():
    z = FakeSummarizer({})
    z.lead = 2                                  # third candidate: the tech story
    secs, errors = two_sections(), []
    lead, curio, usage = front_page(z, secs, ["Old fact"], errors)
    assert (lead.story.title, lead.key) == ("T1", "tech")
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
        fetch_recent_curiosities=lambda conn: [{"title": "Old fact", "topic": "Old"}],
        fetch_all_unsent=lambda conn: [article(1, category="tech")]))
    p = pipeline.prepare(None, settings, cap=5)
    assert seen["hours"] == 48
    assert p.previous == {"tech": [{"title": "Old", "summary": None}]}
    assert p.curiosities == [{"title": "Old fact", "topic": "Old"}]


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


def test_run_digest_arranges_before_picking_the_lead(wired, monkeypatch):
    z = FakeSummarizer({"Geopolitics": [status_story("G1"), status_story("G2")]})
    monkeypatch.setattr(pipeline, "_summarizer_or_none", lambda s: z)
    run_digest(wired.settings, send=False)
    assert z.calls == ["Geopolitics", "arrange", "lead", "curiosity"]


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


def test_run_update_section_follows_the_arrange_answer(updating):
    updating.z.highs = [hl("Hack", [1]), hl("War", [2])]          # both from geopolitics feeds
    updating.z.placements = [Placement("tech"), Placement("geopolitics")]
    r = pipeline.run_update(updating.wired.settings, send=False)
    assert "TECH &amp; AI" in r.digest.html and "GEOPOLITICS" in r.digest.html
    assert updating.z.calls == ["highlights", "arrange"]


def test_run_update_merge_below_minimum_sends_nothing(updating):
    updating.z.highs = [hl("Hack", [1]), hl("Same hack", [2])]
    updating.z.placements = [Placement("geopolitics"), Placement("geopolitics", same_as=0)]
    r = pipeline.run_update(updating.wired.settings, send=True)
    assert r.digest is None and updating.wired.sent == [] and updating.marked == []


def test_run_update_arrange_failure_still_sends(updating):
    updating.z.highs = [hl("A", [1]), hl("B", [2])]
    updating.z.placements = LLMError("no story list")
    r = pipeline.run_update(updating.wired.settings, send=True)
    assert len(updating.wired.sent) == 1 and updating.marked == [[1, 2]]
    assert "arrange: no story list" in r.errors


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


# --------------------------------------------------------------------------- run_weekly
class FakeExpert:
    """expert() answers per section label: None for an analysis, or an exception to raise"""
    label = "fake-weekly"

    def __init__(self, behaviour: dict, overview=None):
        self.behaviour, self.overview_result, self.calls = behaviour, overview, []

    def expert(self, label, description, stories):
        self.calls.append(label)
        result = self.behaviour.get(label)
        if isinstance(result, Exception):
            raise result
        return Analysis(f"{label} analysis", ["P"], []), Usage(20, 8)

    def overview(self, analyses):
        self.calls.append("overview")
        if isinstance(self.overview_result, Exception):
            raise self.overview_result
        return Overview("The week.", "Week subject"), Usage(5, 2)


def week_of(n: int) -> list[dict]:
    return [{"title": f"S{i}", "summary": "s", "sources": [], "status": "new", "previous_title": None}
            for i in range(n)]


@pytest.fixture
def weekly(wired, monkeypatch, sources_cfg):
    z, models, saved = FakeExpert({}), [], []
    monkeypatch.setattr(pipeline, "load_sources", lambda path: sources_cfg)
    monkeypatch.setattr(pipeline, "make_summarizer", lambda s, model=None: models.append(model) or z)
    wired.db.fetch_week_stories = lambda conn: {"geopolitics": week_of(5), "tech": week_of(3)}
    wired.db.digest_sent_within = lambda conn, kind, hours: False
    wired.db.save_digest = lambda conn, kind, *a: saved.append(kind)
    return SimpleNamespace(wired=wired, z=z, models=models, saved=saved, s=wired.settings)


def test_run_weekly_sends_one_analysis_per_section(weekly):
    r = pipeline.run_weekly(weekly.s, send=True)
    assert weekly.z.calls == ["Geopolitics", "Tech & AI", "overview"]
    assert weekly.models == ["gemini-weekly-test"]
    assert len(weekly.wired.sent) == 1 and r.digest.subject == "🧠 Week subject"
    assert weekly.saved == ["weekly"] and "finish_run" in weekly.wired.db.calls
    assert "mark_sent" not in weekly.wired.db.calls
    assert r.considered == 8 and r.usage.input_tokens == 45


def test_run_weekly_skips_sections_with_too_few_stories(weekly):
    weekly.wired.db.fetch_week_stories = lambda conn: {"geopolitics": week_of(5), "tech": week_of(2)}
    r = pipeline.run_weekly(weekly.s, send=True)
    assert weekly.z.calls == ["Geopolitics", "overview"]
    assert "Tech &amp; AI" not in r.digest.html


def test_run_weekly_failed_section_is_skipped(weekly):
    weekly.z.behaviour = {"Geopolitics": LLMError("bad json")}
    r = pipeline.run_weekly(weekly.s, send=True)
    assert weekly.z.calls == ["Geopolitics", "Tech & AI", "overview"]
    assert r.errors == ["expert geopolitics: bad json"] and len(weekly.wired.sent) == 1


def test_run_weekly_quota_stops_the_expert_calls(weekly):
    weekly.z.behaviour = {"Geopolitics": QuotaExhausted("daily quota")}
    with pytest.raises(LLMError, match="no section could be analysed"):
        pipeline.run_weekly(weekly.s, send=True)
    assert weekly.z.calls == ["Geopolitics"]


def test_run_weekly_every_section_failing_fails_the_run(weekly):
    weekly.z.behaviour = {"Geopolitics": LLMError("x"), "Tech & AI": LLMError("y")}
    with pytest.raises(LLMError, match="expert geopolitics: x; expert tech: y"):
        pipeline.run_weekly(weekly.s, send=True)
    assert weekly.wired.sent == [] and weekly.saved == []
    assert "finish_run" in weekly.wired.db.calls


def test_run_weekly_overview_failure_still_sends(weekly):
    weekly.z.overview_result = LLMError("cut off")
    r = pipeline.run_weekly(weekly.s, send=True)
    assert r.digest.subject.startswith("🧠 Khabar Artificial Expert · week of ")
    assert "THE WEEK IN ONE PARAGRAPH" not in r.digest.html
    assert r.errors == ["overview: cut off"] and len(weekly.wired.sent) == 1


def test_run_weekly_guard_blocks_a_second_send(weekly):
    weekly.wired.db.digest_sent_within = lambda conn, kind, hours: kind == "weekly" and hours == 20
    r = pipeline.run_weekly(weekly.s, send=True)
    assert r.digest is None and weekly.z.calls == [] and weekly.wired.sent == []


def test_run_weekly_preview_sends_nothing_and_ignores_the_guard(weekly):
    weekly.wired.db.digest_sent_within = lambda conn, kind, hours: True
    r = pipeline.run_weekly(weekly.s, send=False)
    assert r.digest is not None and weekly.wired.sent == [] and weekly.saved == []
