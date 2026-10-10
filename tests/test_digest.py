from datetime import datetime

import pytest

from app.digest import Section, build_headlines, build_summary_digest, slot_label
from app.llm import Story

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


def test_summary_digest_content():
    d = build_summary_digest([Section("geo", "Geopolitics", stories=[story(), story("Other", single=True)])], TZ)
    assert "2 stories" in d.subject
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


def test_build_headlines_follows_category_order_and_skips_empty():
    rows = [headline(1, "T1", category="tech"), headline(2, "G1", category="geo"), headline(3, "X", category="unknown")]
    d = build_headlines(rows, {"geo": "Geo", "tech": "Tech", "science": "Science"}, TZ)
    assert [s["category"] for s in d.payload["sections"]] == ["geo", "tech"]
    assert "Science" not in d.html
    assert "https://h.test/3" not in d.html      # undeclared category is not shown
    assert "headlines only" not in d.html
    assert "2 stories" in d.subject
