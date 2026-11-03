from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from app.llm import Curiosity, Story

FONT = "-apple-system,'Segoe UI',Roboto,Arial,sans-serif"

# Nuqta tokens (brand/email-mockup/HANDOFF.md)
PAPER, INK, MUTED, RULE = "#fbfcfb", "#101f1c", "#4a5955", "#e3e7e6"
GREEN, AMBER, KICKER, ASIDE, ON_GREEN = "#0b5d4f", "#cf7f00", "#f3c26b", "#f6eedc", "#f7faf8"
MARKS = "https://raw.githubusercontent.com/Mainich-Mohamed/Khabar/main/brand/email-mockup/assets"
_SOURCE_LINK = "text-decoration:underline;display:inline-block;padding:10px 14px 10px 0;line-height:24px"
_LINK_ON_PAPER = f"color:{GREEN};{_SOURCE_LINK}"
_HEADLINE_LINK = f"color:{GREEN};text-decoration:underline"
COUNT_WORDS = {2: "Two", 3: "Three", 4: "Four", 5: "Five"}   # MIN_UPDATE_STORIES to MAX_UPDATE_STORIES

DARK_CSS = """@media (prefers-color-scheme: dark) {
  .canvas, .paper, .paper td { background-color:#06120f !important; }
  .aside, .aside td { background-color:#14241f !important; }
  .ink { color:#f1f4f3 !important; }
  .muted { color:#99a4a1 !important; }
  .link a, .tagc, .num { color:#54a896 !important; }
  .rule { border-top-color:#354541 !important; }
  .light-only { display:none !important; }
  .dark-only { display:inline-block !important; }
}"""


@dataclass
class Digest:
    subject: str
    html: str
    text: str
    payload: dict = field(default_factory=dict)


@dataclass
class Section:
    key: str
    label: str
    stories: list[Story] = field(default_factory=list)   # summary mode
    headlines: list[dict] = field(default_factory=list)  # fallback mode
    dropped: list[Story] = field(default_factory=list)   # repeats of earlier stories: payload only, never shown

    @property
    def is_fallback(self) -> bool:
        return not self.stories and not self.dropped

    def count(self) -> int:
        return len(self.stories) or len(self.headlines)


@dataclass
class Lead:
    key: str               # category of the story
    label: str
    story: Story


@dataclass
class UpdateItem:
    key: str               # category of the story
    label: str
    story: Story


def slot_label(now: datetime) -> str:
    if now.hour < 12:
        return "Morning"
    if now.hour < 18:
        return "Afternoon"
    return "Evening"


def _band(content: str, bg: str = PAPER, cls: str = "paper", padding: str = "0 28px") -> str:
    """One full-width coloured row holding a centred 600px column"""
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" class="{cls}" '
        f'bgcolor="{bg}" style="background-color:{bg}"><tr><td align="center">'
        '<!--[if mso]><table role="presentation" width="600" cellpadding="0" cellspacing="0"><tr><td><![endif]-->'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:600px"><tr><td style="padding:{padding};font-family:{FONT}">{content}</td></tr></table>'
        "<!--[if mso]></td></tr></table><![endif]--></td></tr></table>"
    )


def _header(edition: str, detail: str) -> str:
    marks = (
        f'<img class="light-only" src="{MARKS}/mark-light.png" width="30" height="30" alt="" '
        'style="vertical-align:-7px;margin-right:8px">'
        f'<img class="dark-only" src="{MARKS}/mark-dark.png" width="30" height="30" alt="" '
        'style="display:none;vertical-align:-7px;margin-right:8px">'
    )
    return _band(
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td class="ink" style="font-size:25px;font-weight:700;color:{INK}">{marks}khabar</td>'
        f'<td class="muted" align="right" style="font-size:13px;color:{MUTED}">{escape(edition)}'
        f'<br><span style="font-size:12px">{escape(detail)}</span></td>'
        "</tr></table>",
        padding="22px 28px 16px",
    )


def _page(title: str, teaser: str, bands: list[str]) -> str:
    hidden = (f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all">{escape(teaser)}</div>'
              if teaser else "")   # shown by inboxes after the subject, hidden in the email itself
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">'
        f"<title>{escape(title)}</title><style>{DARK_CSS}</style></head>"
        f'<body class="canvas" style="margin:0;padding:0;background-color:{PAPER}">{hidden}{"".join(bands)}</body></html>'
    )


def _link(url: str, text: str, style: str) -> str:
    return f'<a href="{escape(url, quote=True)}" style="{style}">{escape(text)}</a>'


def _sources(st: Story, color: str = GREEN) -> str:
    return "".join(_link(s["url"], s["name"], f"color:{color};{_SOURCE_LINK}") for s in st.sources)


def _section_head(label: str) -> str:
    return (f'<div class="ink" style="font-size:13px;font-weight:700;letter-spacing:.06em;color:{INK};'
            f'padding-bottom:12px"><span style="color:{AMBER};font-size:11px">&#9679;</span>&nbsp; {escape(label)}</div>')


def _story(st: Story) -> str:
    """Title, summary and source links; shared by the full brief and the update"""
    is_update = st.status == "update" and st.previous_title
    tag = (f'<span class="tagc" style="color:{GREEN};font-size:13px;margin-right:6px">Update</span>'
           if is_update else "")
    earlier = (f'<div class="muted" style="font-size:13px;color:{MUTED};padding-top:3px">'
               f"Earlier: {escape(st.previous_title)}</div>" if is_update else "")
    flag = (f'<span class="muted" style="color:{MUTED};font-size:12px">single source</span>'
            if st.single_source else "")
    return (
        f'<div class="ink" style="font-size:18px;font-weight:700;line-height:1.3;color:{INK}">{tag}{escape(st.title)}</div>'
        f"{earlier}"
        f'<div class="ink" style="font-size:16px;line-height:1.5;color:{INK};padding-top:5px">{escape(st.summary)}</div>'
        f'<div class="link" style="font-size:13px">{_sources(st)}{flag}</div>'
    )


def _rule() -> str:
    return f'<div class="rule" style="border-top:1px solid {RULE};font-size:0;line-height:0;margin-bottom:14px">&nbsp;</div>'


def _footer(*lines: str) -> str:
    text = "".join(f'<div class="muted" style="font-size:12px;line-height:1.5;color:{MUTED}">{escape(x)}</div>'
                   for x in lines)
    return _band(_rule() + text, padding="24px 28px 32px")


def _update_item(n: int, it: UpdateItem) -> str:
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td class="num" width="8%" valign="top" style="font-size:22px;font-weight:700;line-height:1.2;color:{GREEN}">{n}</td>'
        '<td valign="top" style="padding-bottom:6px">'
        f'<div class="muted" style="font-size:12px;font-weight:700;letter-spacing:.08em;color:{MUTED};padding-bottom:3px">'
        f"{escape(it.label.upper())}</div>{_story(it.story)}</td></tr></table>"
    )


def build_summary_digest(sections: list[Section], tz: str, fallback_note: bool = True,
                         lead: Lead | None = None, curiosity: Curiosity | None = None) -> Digest:
    now = datetime.now(ZoneInfo(tz))
    slot = slot_label(now)
    recorded = [s for s in sections if s.count() or s.dropped]   # payload also keeps repeat-only sections
    sections = [s for s in sections if s.count()]
    total = sum(s.count() for s in sections) + (1 if lead else 0)
    # The top story sells the email in the inbox; without summaries, keep the plain subject
    top = lead.story.title if lead else next((st.title for s in sections for st in s.stories), None)
    if top:
        subject = f"🗞 {top}"
    else:
        subject = f"🗞 {slot} brief · {now:%a %d %b} — " + (f"{total} stories" if total else "nothing new")
    # Preview text: the first story of the next sections, shown by inboxes after the subject
    teaser = " · ".join([s.stories[0].title for s in sections if s.stories and s.stories[0].title != top][:3])

    bands = [_header(f"{slot} brief", f"{now:%a %d %b} · {total} stories")]
    t = [f"{slot} brief — {now:%A %d %B %Y, %H:%M}", ""]

    if not sections and not lead:
        bands.append(_band(f'<div class="ink" style="font-size:16px;color:{INK};padding:16px 0">'
                           "Nothing new since the last digest.</div>"))
        t.append("Nothing new since the last digest.")

    if lead:
        st = lead.story
        body = f"color:{ON_GREEN};font-size:16px;line-height:1.55;padding-top:10px"
        bands.append(_band(
            f'<div style="color:{KICKER};font-size:12px;font-weight:700;letter-spacing:.08em">'
            f"TOP STORY · {escape(lead.label.upper())}</div>"
            f'<div style="color:{ON_GREEN};font-size:25px;font-weight:700;line-height:1.22;padding-top:8px">'
            f"{escape(st.title)}</div>"
            f'<div style="{body}">{escape(st.summary)}</div>'
            f'<div style="font-size:13px;padding-top:2px">{_sources(st, ON_GREEN)}</div>',
            bg=GREEN, cls="lead", padding="24px 28px 12px",
        ))
        t += ["TOP STORY", "", f"* {st.title}", f"  {st.summary}"]
        t += [f"  - {s['name']}: {s['url']}" for s in st.sources]
        t.append("")

    for sec in sections:
        parts = [_section_head(sec.label)]
        t += [sec.label.upper(), ""]

        if sec.is_fallback:
            if fallback_note:
                parts.append(f'<div class="muted" style="font-size:12px;color:{MUTED};padding-bottom:8px">'
                             "Summaries unavailable for this run — headlines only.</div>")
            for r in sec.headlines:
                parts.append(
                    '<div class="link" style="font-size:16px;line-height:1.4;padding-bottom:10px">'
                    f'{_link(r["url"], r["title"], _HEADLINE_LINK)} '
                    f'<span class="muted" style="color:{MUTED};font-size:12px">{escape(r["source"])}</span></div>'
                )
                t.append(f"- {r['title']} ({r['source']})\n  {r['url']}")
            t.append("")
        else:
            parts.append(_rule().join(_story(st) for st in sec.stories))
            for st in sec.stories:
                is_update = st.status == "update" and st.previous_title
                t.append(f"* [Update] {st.title}" if is_update else f"* {st.title}")
                if is_update:
                    t.append(f"  Earlier: {st.previous_title}")
                t.append(f"  {st.summary}")
                for s in st.sources:
                    t.append(f"  - {s['name']}: {s['url']}")
                if st.single_source:
                    t.append("  (single source)")
                t.append("")
        bands.append(_band("".join(parts), padding="26px 28px 20px"))

    if curiosity:
        bands.append(_band(
            _section_head("Did you know?")
            + f'<div class="ink" style="font-size:18px;font-weight:700;line-height:1.3;color:{INK}">'
              f"{escape(curiosity.title)}</div>"
              f'<div class="ink" style="font-size:16px;line-height:1.5;color:{INK};padding-top:4px">'
              f"{escape(curiosity.text)}</div>"
              f'<div class="link" style="font-size:13px">'
              f'{_link(curiosity.url, "Learn more", _LINK_ON_PAPER)}'
              f'<span class="muted" style="color:{MUTED};font-size:12px">'
              "From general knowledge, not from today's news</span></div>",
            bg=ASIDE, cls="aside", padding="24px 28px 22px",
        ))
        t += ["DID YOU KNOW?", "", f"* {curiosity.title}", f"  {curiosity.text}",
              f"  Learn more: {curiosity.url}", "  (From general knowledge, not from today's news)", ""]

    bands.append(_footer("AI-generated from the linked articles. Check the source before relying on a detail."))
    html = _page(f"Khabar · {slot} brief", teaser, bands)

    payload = {
        "generated_at": now.isoformat(),
        "slot": slot.lower(),
        "sections": [
            {
                "category": s.key,
                "label": s.label,
                "mode": "headlines" if s.is_fallback else "summary",
                "stories": [st.to_dict() for st in s.stories]
                if not s.is_fallback
                else [{"title": r["title"], "sources": [{"name": r["source"], "url": r["url"]}]}
                      for r in s.headlines],
                "dropped": [{"title": st.title, "repeat_of": st.previous_title} for st in s.dropped],
            }
            for s in recorded
        ],
    }
    if lead:
        payload["lead"] = {**lead.story.to_dict(), "category": lead.key, "label": lead.label}
    if curiosity:
        payload["curiosity"] = curiosity.to_dict()
    return Digest(subject=subject, html=html, text="\n".join(t), payload=payload)


def build_update_digest(items: list[UpdateItem], tz: str) -> Digest:
    """The short mid-day email: the few stories that could not wait for the full brief, in importance order"""
    now = datetime.now(ZoneInfo(tz))
    slot = slot_label(now)
    subject = f"⚡ {items[0].story.title}"
    teaser = " · ".join(it.story.title for it in items[1:3])

    count = COUNT_WORDS.get(len(items), str(len(items)))
    bands = [
        _header(f"{slot} update", f"{now:%a %d %b} · {len(items)} stories"),
        _band(f'<div class="muted" style="font-size:15px;color:{MUTED};padding-bottom:14px">'
              f"{count} things since this morning.</div>{_rule()}", padding="16px 28px 0"),
        _band("".join(_update_item(n, it) for n, it in enumerate(items, start=1)), padding="4px 28px 0"),
        _footer("The full brief comes this evening.",
                "AI-generated from the linked articles. Check the source before relying on a detail."),
    ]
    t = [f"{slot} update — {now:%A %d %B %Y, %H:%M}", ""]

    for n, it in enumerate(items, start=1):
        st = it.story
        is_update = st.status == "update" and st.previous_title
        t.append(f"{n}. [Update] {st.title}" if is_update else f"{n}. {st.title}")
        t.append(f"   {it.label}")
        if is_update:
            t.append(f"   Earlier: {st.previous_title}")
        t.append(f"   {st.summary}")
        t += [f"   - {s['name']}: {s['url']}" for s in st.sources]
        if st.single_source:
            t.append("   (single source)")
        t.append("")

    t.append("The full brief comes this evening.")

    sections: dict[str, dict] = {}   # same payload shape as a full brief, so history code reads both
    for it in items:
        sec = sections.setdefault(it.key, {"category": it.key, "label": it.label, "mode": "summary",
                                           "stories": [], "dropped": []})
        sec["stories"].append(it.story.to_dict())
    payload = {"generated_at": now.isoformat(), "slot": slot.lower(), "sections": list(sections.values())}
    html = _page(f"Khabar · {slot} update", teaser, bands)
    return Digest(subject=subject, html=html, text="\n".join(t), payload=payload)


def build_headlines(rows: list[dict], categories: dict[str, str], tz: str) -> Digest:
    """Raw headlines grouped by category. Kept for `run-headlines` and as a debugging tool"""
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    sections = [Section(key=k, label=label, headlines=by_cat[k]) for k, label in categories.items() if by_cat.get(k)]
    return build_summary_digest(sections, tz, fallback_note=False)
