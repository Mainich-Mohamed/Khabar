from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from app.llm import Story

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

    @property
    def is_fallback(self) -> bool:
        return not self.stories

    def count(self) -> int:
        return len(self.stories) or len(self.headlines)


def slot_label(now: datetime) -> str:
    if now.hour < 12:
        return "Morning"
    if now.hour < 18:
        return "Afternoon"
    return "Evening"


def _link(url: str, text: str, style: str = "color:#1a56db;text-decoration:none") -> str:
    return f'<a href="{escape(url, quote=True)}" style="{style}">{escape(text)}</a>'

def build_summary_digest(sections: list[Section], tz: str, fallback_note: bool = True) -> Digest:
    now = datetime.now(ZoneInfo(tz))
    slot = slot_label(now)
    sections = [s for s in sections if s.count()]
    total = sum(s.count() for s in sections)
    subject = f"🗞 {slot} brief · {now:%a %d %b} — " + (f"{total} stories" if total else "nothing new")

    h = [
        f'<div style="font-family:{FONT};max-width:640px;margin:0 auto;color:#1a1a1a;line-height:1.5">',
        f'<h2 style="margin:0 0 4px">{slot} brief</h2>',
        f'<div style="color:#666;font-size:13px;margin-bottom:8px">{now:%A %d %B %Y, %H:%M} · {total} stories</div>',
    ]
    t = [f"{slot} brief — {now:%A %d %B %Y, %H:%M}", ""]

    if not sections:
        h.append("<p>Nothing new since the last digest.</p>")
        t.append("Nothing new since the last digest.")

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
            links = " · ".join(_link(s["url"], s["name"], "color:#666;text-decoration:underline")
                               for s in st.sources)
            flag = (' <span style="color:#b45309;font-size:11px">· single source</span>'
                    if st.single_source else "")
            h.append(
                '<div style="margin-bottom:18px">'
                f'<div style="font-weight:600;font-size:15px;margin-bottom:3px">{escape(st.title)}</div>'
                f'<div style="font-size:14px;color:#333">{escape(st.summary)}</div>'
                f'<div style="font-size:12px;color:#888;margin-top:4px">{links}{flag}</div>'
                "</div>"
            )
            t.append(f"* {st.title}")
            t.append(f"  {st.summary}")
            for s in st.sources:
                t.append(f"  - {s['name']}: {s['url']}")
            if st.single_source:
                t.append("  (single source)")
            t.append("")

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
            }
            for s in sections
        ],
    }
    return Digest(subject=subject, html="\n".join(h), text="\n".join(t), payload=payload)


def build_headlines(rows: list[dict], categories: dict[str, str], tz: str) -> Digest:
    """Raw headlines grouped by category. Kept for `run-headlines` and as a debugging tool"""
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    sections = [Section(key=k, label=label, headlines=by_cat[k]) for k, label in categories.items() if by_cat.get(k)]
    return build_summary_digest(sections, tz, fallback_note=False)
