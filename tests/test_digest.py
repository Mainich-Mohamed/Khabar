from datetime import datetime

import pytest

from app.digest import (Lead, Section, UpdateItem, WeeklySection, build_headlines, build_summary_digest,
                        build_update_digest, build_weekly_digest, slot_label)
from app.llm import Analysis, Curiosity, Overview, Story

TZ = "Africa/Casablanca"


def story(title="Rates rise", summary="The bank raised rates.", single=False) -> Story:
    sources = [{"name": "BBC", "url": "https://bbc.test/1"}]
    if not single:
        sources.append({"name": "DW", "url": "https://dw.test/2"})
    return Story(title=title, summary=summary, sources=sources, single_source=single, article_ids=[1, 2])


def headline(id_, title="Headline", source="Wire", category="geopolitics"):
    return {"id": id_, "title": title, "source": source, "url": f"https://h.test/{id_}", "category": category}


@pytest.mark.parametrize("hour, label", [(0, "Morning"), (7, "Morning"), (11, "Morning"),
                                         (12, "Afternoon"), (17, "Afternoon"),
                                         (18, "Evening"), (23, "Evening")])
def test_slot_label(hour, label):
    assert slot_label(datetime(2026, 10, 10, hour)) == label


def test_section_modes():
    assert Section("k", "K", stories=[story()]).is_fallback is False
    fb = Section("k", "K", headlines=[headline(1), headline(2)])
    assert fb.is_fallback is True and fb.count() == 2
    assert Section("k", "K").count() == 0
    assert Section("k", "K", dropped=[story()]).is_fallback is False


def test_summary_digest_content():
    d = build_summary_digest([Section("geo", "Geopolitics", stories=[story(), story("Other", single=True)])], TZ)
    assert d.subject == "🗞 Rates rise" and "2 stories" in d.html
    assert "Geopolitics" in d.html and "Rates rise" in d.html
    assert 'href="https://bbc.test/1"' in d.html and 'href="https://dw.test/2"' in d.html
    assert d.html.count("single source") == 1
    assert "AI-generated" in d.html
    assert "GEOPOLITICS" in d.text and "- DW: https://dw.test/2" in d.text and "(single source)" in d.text


def test_summary_digest_escapes_html():
    evil = story(title="<script>alert(1)</script>", summary="A & B")
    evil.sources = [{"name": "<b>X</b>", "url": 'https://x.test/?a=1&b="2"'}]
    d = build_summary_digest([Section("geo", "Geo <World>", stories=[evil])], TZ)
    assert "<script>" not in d.html
    assert "&lt;script&gt;" in d.html and "A &amp; B" in d.html and "Geo &lt;World&gt;" in d.html
    assert "<b>X</b>" not in d.html
    assert 'href="https://x.test/?a=1&amp;b=&quot;2&quot;"' in d.html


def test_summary_digest_fallback_section():
    d = build_summary_digest([Section("tech", "Tech", headlines=[headline(1, "Chip news", "Ars")])], TZ)
    assert "headlines only" in d.html
    assert "Chip news" in d.html and "Ars" in d.html
    assert "- Chip news (Ars)" in d.text
    assert d.payload["sections"][0]["mode"] == "headlines"
    assert d.payload["sections"][0]["stories"] == [
        {"title": "Chip news", "sources": [{"name": "Ars", "url": "https://h.test/1"}]}]


def test_summary_digest_fallback_note_can_be_hidden():
    d = build_summary_digest([Section("tech", "Tech", headlines=[headline(1)])], TZ, fallback_note=False)
    assert "headlines only" not in d.html


def test_summary_digest_empty_sections_dropped_and_nothing_new():
    d = build_summary_digest([Section("a", "Empty"), Section("b", "Also empty")], TZ)
    assert "nothing new" in d.subject
    assert "Nothing new since the last digest." in d.html and "Nothing new" in d.text
    assert "Empty" not in d.html
    assert d.payload["sections"] == []


def test_summary_digest_payload():
    d = build_summary_digest([Section("geo", "Geopolitics", stories=[story()]),
                              Section("tech", "Tech", headlines=[headline(9)])], TZ)
    p = d.payload
    assert p["slot"] in {"morning", "afternoon", "evening"}
    assert datetime.fromisoformat(p["generated_at"]).tzinfo is not None
    assert [s["category"] for s in p["sections"]] == ["geo", "tech"]
    assert p["sections"][0]["mode"] == "summary"
    assert p["sections"][0]["stories"][0] == story().to_dict()


def update_story(title="Ceasefire broken", previous="Ceasefire agreed") -> Story:
    st = story(title=title)
    st.status, st.previous_title = "update", previous
    return st


def repeat_story(title="Rates still held", previous="Rates held") -> Story:
    st = story(title=title)
    st.status, st.previous_title = "repeat", previous
    return st


def test_update_story_has_badge_and_earlier_line():
    d = build_summary_digest([Section("geo", "Geo", stories=[update_story(), story("Fresh news")])], TZ)
    assert d.html.count(">Update</span>") == 1                    # only the update, not the new story
    assert "Earlier: Ceasefire agreed" in d.html
    assert "* [Update] Ceasefire broken\n  Earlier: Ceasefire agreed" in d.text
    assert "* Fresh news" in d.text


def test_update_earlier_line_is_escaped():
    d = build_summary_digest([Section("geo", "Geo", stories=[update_story(previous="<b>Old</b>")])], TZ)
    assert "<b>Old</b>" not in d.html and "Earlier: &lt;b&gt;Old&lt;/b&gt;" in d.html


def test_repeats_are_not_shown_but_recorded_in_payload():
    d = build_summary_digest([Section("geo", "Geo", stories=[story()], dropped=[repeat_story()])], TZ)
    assert "Rates still held" not in d.html and "Rates still held" not in d.text
    assert "1 stories" in d.html
    assert d.payload["sections"][0]["dropped"] == [{"title": "Rates still held", "repeat_of": "Rates held"}]


def test_repeat_only_section_is_hidden_but_kept_in_payload():
    d = build_summary_digest([Section("geo", "Geo", dropped=[repeat_story()])], TZ)
    assert "nothing new" in d.subject and "Geo" not in d.html
    [sec] = d.payload["sections"]
    assert sec["mode"] == "summary" and sec["stories"] == []
    assert sec["dropped"] == [{"title": "Rates still held", "repeat_of": "Rates held"}]


def test_build_headlines_follows_category_order_and_skips_empty():
    rows = [headline(1, "T1", category="tech"), headline(2, "G1", category="geo"), headline(3, "X", category="unknown")]
    d = build_headlines(rows, {"geo": "Geo", "tech": "Tech", "science": "Science"}, TZ)
    assert [s["category"] for s in d.payload["sections"]] == ["geo", "tech"]
    assert "Science" not in d.html
    assert "https://h.test/3" not in d.html      # undeclared category is not shown
    assert "headlines only" not in d.html
    assert "2 stories" in d.subject


# --------------------------------------------------------------------------- front page
def lead(title="Truce agreed") -> Lead:
    return Lead(key="geo", label="Geopolitics", story=story(title))


CURIO = Curiosity(title="War on emus", text="Australia once fought emus.", topic="Emu War")


def test_lead_is_shown_first_and_used_as_subject():
    d = build_summary_digest([Section("eco", "Economy", stories=[story()])], TZ, lead=lead())
    assert d.subject == "🗞 Truce agreed"
    assert d.html.index("TOP STORY · GEOPOLITICS") < d.html.index("Economy")
    assert "The bank raised rates." in d.html and "2 stories" in d.html
    assert "TOP STORY" in d.text
    assert "Why it matters" not in d.html and "Why it matters" not in d.text


def test_lead_alone_is_not_nothing_new():
    d = build_summary_digest([], TZ, lead=lead())
    assert "Nothing new" not in d.html and d.subject.startswith("🗞 Truce agreed")


def test_subject_without_lead_uses_first_story():
    d = build_summary_digest([Section("geo", "Geo", stories=[story("First"), story("Second")])], TZ)
    assert d.subject == "🗞 First"


def test_subject_headlines_only_keeps_count_format():
    d = build_summary_digest([Section("tech", "Tech", headlines=[headline(1)])], TZ)
    assert "1 stories" in d.subject


def test_preview_text_lists_next_sections_and_skips_the_subject_story():
    secs = [Section(k, k, stories=[story(f"{k} top"), story(f"{k} second")]) for k in ("A", "B", "C", "D")]
    d = build_summary_digest(secs, TZ)
    teaser = d.html.split("</div>", 1)[0]
    assert "display:none" in teaser
    assert "B top · C top · D top" in teaser        # "A top" is already the subject
    assert "second" not in teaser


def test_curiosity_at_the_end_with_built_link():
    d = build_summary_digest([Section("geo", "Geo", stories=[story()])], TZ, curiosity=CURIO)
    assert d.html.index("Did you know?") > d.html.index("Rates rise")
    assert 'href="https://en.wikipedia.org/w/index.php?search=Emu+War"' in d.html
    assert "not from today's news" in d.html
    assert "Learn more: https://en.wikipedia.org/w/index.php?search=Emu+War" in d.text


def test_payload_records_lead_and_curiosity():
    d = build_summary_digest([Section("eco", "Economy", stories=[story()])], TZ, lead=lead(), curiosity=CURIO)
    assert d.payload["lead"]["title"] == "Truce agreed"
    assert d.payload["lead"]["category"] == "geo" and "why_it_matters" not in d.payload["lead"]
    assert d.payload["curiosity"]["url"].endswith("Emu+War")
    assert "lead" not in build_summary_digest([], TZ).payload


# --------------------------------------------------------------------------- update digest
def item(title="Truce agreed", key="geo", label="Geopolitics", st=None) -> UpdateItem:
    return UpdateItem(key=key, label=label, story=st or story(title))


def test_update_digest_is_flat_numbered_and_headline_subject():
    d = build_update_digest([item("First"), item("Second", "eco", "Economy")], TZ)
    assert d.subject == "⚡ First"
    assert d.html.index("First") < d.html.rindex("Second")    # rindex: the teaser also names the second story
    assert "Two things since this morning." in d.html
    assert "GEOPOLITICS" in d.html and "ECONOMY" in d.html and "2 stories" in d.html
    assert "The full brief comes this evening." in d.html and "DID YOU KNOW" not in d.html
    assert "1. First" in d.text and "2. Second" in d.text and "- DW: https://dw.test/2" in d.text


def test_update_digest_shows_update_badge_and_single_source():
    d = build_update_digest([item(st=update_story()), item("Solo", st=story("Solo", single=True))], TZ)
    assert d.html.count(">Update</span>") == 1 and "Earlier: Ceasefire agreed" in d.html
    assert d.html.count("single source") == 1
    assert "1. [Update] Ceasefire broken" in d.text


def test_update_digest_escapes_html():
    d = build_update_digest([item(st=story(title="<script>x</script>", summary="A & B"), label="Geo <W>")], TZ)
    assert "<script>" not in d.html and "A &amp; B" in d.html and "GEO &lt;W&gt;" in d.html   # label is upper-cased, then escaped


def test_update_digest_payload_groups_by_category_like_a_full_brief():
    d = build_update_digest([item("A1"), item("B1", "eco", "Economy"), item("A2")], TZ)
    assert [s["category"] for s in d.payload["sections"]] == ["geo", "eco"]
    assert [st["title"] for st in d.payload["sections"][0]["stories"]] == ["A1", "A2"]
    assert d.payload["sections"][0]["mode"] == "summary"
    assert d.payload["slot"] in {"morning", "afternoon", "evening"}


# --------------------------------------------------------------------------- weekly digest
REF = {"title": "Rates rise", "sources": [{"name": "BBC", "url": "https://bbc.test/1"}]}
OVERVIEW = Overview(intro="The week in short.", subject="Money got expensive")


def weekly(title="Expensive money", paragraphs=("First point.", "Second point."), refs=(REF,), key="eco",
           label="Economy") -> WeeklySection:
    return WeeklySection(key=key, label=label,
                         analysis=Analysis(title=title, paragraphs=list(paragraphs), references=list(refs)))


def test_weekly_digest_with_overview():
    d = build_weekly_digest([weekly(), weekly("Chips", key="tech", label="Tech")], TZ, OVERVIEW)
    assert d.subject == "🧠 Money got expensive"
    # ">...</div>": the rendered titles, not the hidden teaser at the top that also names them
    assert (d.html.index("THE WEEK IN ONE PARAGRAPH") < d.html.index(">Expensive money</div>")
            < d.html.index(">Chips</div>"))
    assert "The week in short." in d.html and "<p" in d.html and "First point." in d.html
    assert "BASED ON THIS WEEK" in d.html and 'href="https://bbc.test/1"' in d.html
    assert "Khabar Artificial Expert" in d.html and "2 sections" in d.html
    assert "not established fact" in d.html


def test_weekly_digest_without_overview():
    d = build_weekly_digest([weekly()], TZ)
    assert d.subject.startswith("🧠 Khabar Artificial Expert · week of ")
    assert "THE WEEK IN ONE PARAGRAPH" not in d.html and "THE WEEK IN ONE PARAGRAPH" not in d.text


def test_weekly_analysis_without_references_has_no_based_on():
    d = build_weekly_digest([weekly(refs=())], TZ, OVERVIEW)
    assert "BASED ON" not in d.html and "Based on" not in d.text


def test_weekly_digest_escapes_html():
    evil = {"title": "<b>Ref</b>", "sources": [{"name": "X", "url": "https://x.test/?a=1&b=2"}]}
    d = build_weekly_digest([weekly(title="<script>x</script>", paragraphs=["A & B"], refs=[evil])], TZ,
                            Overview(intro="<i>hi</i>", subject="S"))
    assert "<script>" not in d.html and "&lt;script&gt;" in d.html and "A &amp; B" in d.html
    assert "<b>Ref</b>" not in d.html and "<i>hi</i>" not in d.html
    assert 'href="https://x.test/?a=1&amp;b=2"' in d.html


def test_weekly_digest_text_version():
    d = build_weekly_digest([weekly()], TZ, OVERVIEW)
    assert "ECONOMY\n\nExpensive money\n\nFirst point.\n" in d.text
    assert "Based on this week's stories:\n* Rates rise\n  - BBC: https://bbc.test/1" in d.text
    assert d.text.endswith("not established fact.")


def test_weekly_digest_payload():
    d = build_weekly_digest([weekly(), weekly(key="tech", label="Tech")], TZ, OVERVIEW)
    assert [s["category"] for s in d.payload["sections"]] == ["eco", "tech"]
    assert d.payload["sections"][0]["analysis"] == weekly().analysis.to_dict()
    assert d.payload["overview"] == {"intro": "The week in short.", "subject": "Money got expensive"}
    assert "stories" not in d.payload["sections"][0]
    assert "overview" not in build_weekly_digest([weekly()], TZ).payload
