from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from app.llm import Curiosity, Story

FONT = "-apple-system,Segoe UI,Roboto,Arial,sans-serif"


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
    why_it_matters: str


def slot_label(now: datetime) -> str:
    if now.hour < 12:
        return "Morning"
    if now.hour < 18:
        return "Afternoon"
    return "Evening"


def _link(url: str, text: str, style: str = "color:#1a56db;text-decoration:none") -> str:
    return f'<a href="{escape(url, quote=True)}" style="{style}">{escape(text)}</a>'


def _source_links(st: Story) -> str:
    return " · ".join(_link(s["url"], s["name"], "color:#666;text-decoration:underline") for s in st.sources)


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
        subject = f"🗞 {top} · {slot} brief"
    else:
        subject = f"🗞 {slot} brief · {now:%a %d %b} — " + (f"{total} stories" if total else "nothing new")
    # Preview text: the first story of the next sections, shown by inboxes after the subject
    teaser = " · ".join([s.stories[0].title for s in sections if s.stories and s.stories[0].title != top][:3])

    h = []
    if teaser:   # hidden in the email itself
        h.append(f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all">{escape(teaser)}</div>')
    h += [
        f'<div style="font-family:{FONT};max-width:640px;margin:0 auto;color:#1a1a1a;line-height:1.5">',
        f'<h2 style="margin:0 0 4px">{slot} brief</h2>',
        f'<div style="color:#666;font-size:13px;margin-bottom:8px">{now:%A %d %B %Y, %H:%M} · {total} stories</div>',
    ]
    t = [f"{slot} brief — {now:%A %d %B %Y, %H:%M}", ""]

    if not sections and not lead:
        h.append("<p>Nothing new since the last digest.</p>")
        t.append("Nothing new since the last digest.")

    if lead:
        st = lead.story
        h.append(
            '<div style="margin:20px 0 8px;padding:14px 16px;background:#f3f6fc;border-left:4px solid #1a56db">'
            '<div style="font-size:11px;letter-spacing:.06em;color:#1a56db;font-weight:600;margin-bottom:4px">'
            f"TOP STORY · {escape(lead.label.upper())}</div>"
            f'<div style="font-weight:700;font-size:18px;margin-bottom:4px">{escape(st.title)}</div>'
            f'<div style="font-size:14px;color:#333">{escape(st.summary)}</div>'
            f'<div style="font-size:14px;color:#333;margin-top:6px"><b>Why it matters:</b> '
            f"{escape(lead.why_it_matters)}</div>"
            f'<div style="font-size:12px;color:#888;margin-top:6px">{_source_links(st)}</div>'
            "</div>"
        )
        t += ["TOP STORY", "", f"* {st.title}", f"  {st.summary}", f"  Why it matters: {lead.why_it_matters}"]
        t += [f"  - {s['name']}: {s['url']}" for s in st.sources]
        t.append("")

    for sec in sections:
        h.append(f'<h3 style="margin:28px 0 10px;padding-bottom:4px;border-bottom:1px solid #e5e5e5">'
                 f"{escape(sec.label)}</h3>")
        t += [sec.label.upper(), ""]

        if sec.is_fallback:
            if fallback_note:
                h.append('<div style="color:#999;font-size:12px;margin-bottom:6px">'
                         "Summaries unavailable for this run — headlines only.</div>")
            h.append('<ul style="padding-left:18px;margin:0">')
            for r in sec.headlines:
                h.append(f'<li style="margin-bottom:6px">{_link(r["url"], r["title"])} '
                         f'<span style="color:#888;font-size:12px">— {escape(r["source"])}</span></li>')
                t.append(f"- {r['title']} ({r['source']})\n  {r['url']}")
            h.append("</ul>")
            t.append("")
            continue

        for st in sec.stories:
            links = _source_links(st)
            flag = (' <span style="color:#b45309;font-size:11px">· single source</span>'
                    if st.single_source else "")
            is_update = st.status == "update" and st.previous_title
            badge = ('<span style="color:#fff;background:#1a56db;font-size:11px;padding:1px 6px;'
                     'border-radius:3px;margin-right:6px">Update</span>' if is_update else "")
            earlier = (f'<div style="font-size:12px;color:#888;margin-bottom:3px">'
                       f"Earlier: {escape(st.previous_title)}</div>" if is_update else "")
            h.append(
                '<div style="margin-bottom:18px">'
                f'<div style="font-weight:600;font-size:15px;margin-bottom:3px">{badge}{escape(st.title)}</div>'
                f"{earlier}"
                f'<div style="font-size:14px;color:#333">{escape(st.summary)}</div>'
                f'<div style="font-size:12px;color:#888;margin-top:4px">{links}{flag}</div>'
                "</div>"
            )
            t.append(f"* [Update] {st.title}" if is_update else f"* {st.title}")
            if is_update:
                t.append(f"  Earlier: {st.previous_title}")
            t.append(f"  {st.summary}")
            for s in st.sources:
                t.append(f"  - {s['name']}: {s['url']}")
            if st.single_source:
                t.append("  (single source)")
            t.append("")

    if curiosity:
        h.append(
            '<div style="margin-top:32px;padding:14px 16px;background:#fdf8ec">'
            '<div style="font-size:11px;letter-spacing:.06em;color:#b45309;font-weight:600;margin-bottom:4px">'
            "DID YOU KNOW?</div>"
            f'<div style="font-weight:600;font-size:15px;margin-bottom:3px">{escape(curiosity.title)}</div>'
            f'<div style="font-size:14px;color:#333">{escape(curiosity.text)}</div>'
            '<div style="font-size:12px;color:#888;margin-top:6px">'
            f'{_link(curiosity.url, "Learn more", "color:#666;text-decoration:underline")}'
            " · From general knowledge, not from today's news</div>"
            "</div>"
        )
        t += ["DID YOU KNOW?", "", f"* {curiosity.title}", f"  {curiosity.text}",
              f"  Learn more: {curiosity.url}", "  (From general knowledge, not from today's news)", ""]

    h.append('<p style="color:#aaa;font-size:11px;margin-top:32px">Summaries are AI-generated from the '
             "linked articles. Check the source before relying on a detail.</p></div>")

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
        payload["lead"] = {**lead.story.to_dict(), "category": lead.key, "label": lead.label,
                           "why_it_matters": lead.why_it_matters}
    if curiosity:
        payload["curiosity"] = curiosity.to_dict()
    return Digest(subject=subject, html="\n".join(h), text="\n".join(t), payload=payload)


def build_headlines(rows: list[dict], categories: dict[str, str], tz: str) -> Digest:
    """Raw headlines grouped by category. Kept for `run-headlines` and as a debugging tool"""
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    sections = [Section(key=k, label=label, headlines=by_cat[k]) for k, label in categories.items() if by_cat.get(k)]
    return build_summary_digest(sections, tz, fallback_note=False)
