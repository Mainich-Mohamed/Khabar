"""The digest run: ingest -> select -> extract -> summarize -> email -> store"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app import db
from app.config import Settings, SourcesConfig, load_sources
from app.digest import Digest, Lead, Section, build_summary_digest
from app.emailer import Emailer
from app.extract import extract_leads
from app.ingest import ingest_all
from app.llm import Curiosity, LLMError, QuotaExhausted, Summarizer, Usage, make_summarizer

log = logging.getLogger(__name__)


@dataclass
class Prepared:
    cfg: SourcesConfig
    unsent: list[dict]                    # every unsent article in the window
    candidates: dict[str, list[dict]]     # category -> ranked articles (lead extracted)
    new_articles: int
    errors: list[str]
    previous: dict[str, list[dict]] = field(default_factory=dict)   # category -> stories sent recently
    curiosities: list[str] = field(default_factory=list)            # recent "Did you know?" titles


@dataclass
class RunResult:
    digest: Digest
    new_articles: int
    considered: int
    usage: Usage
    errors: list[str]


def make_emailer(s: Settings) -> Emailer:
    return Emailer(s.smtp_host, s.smtp_port, s.smtp_user, s.smtp_password, s.email_to)


def rank(articles: list[dict], cfg: SourcesConfig) -> list[dict]:
    """Trusted and recent first. Step 3 will add 'number of outlets covering it'"""
    now = datetime.now(timezone.utc)

    def score(a: dict) -> float:
        hours_old = max((now - a["published_at"]).total_seconds() / 3600, 0)
        return cfg.weight(a["source"]) / (1 + hours_old / 12)

    return sorted(articles, key=score, reverse=True)


def prepare(conn, s: Settings, cap: int) -> Prepared:
    cfg = load_sources(s.sources_path)
    new, errors = ingest_all(conn, cfg.sources, db.insert_article)
    unsent = db.fetch_all_unsent(conn)
    by_cat: dict[str, list[dict]] = {}
    for a in unsent:
        by_cat.setdefault(a["category"], []).append(a)
    candidates = {k: rank(v, cfg)[:cap] for k, v in by_cat.items()}
    extract_leads(conn, [a for v in candidates.values() for a in v], db.save_lead)
    previous = db.fetch_recent_stories(conn, s.update_lookback_hours)
    curiosities = db.fetch_recent_curiosities(conn)
    return Prepared(cfg, unsent, candidates, new, errors, previous, curiosities)


def summarize_sections(summarizer: Summarizer | None, p: Prepared, s: Settings,
                       errors: list[str]) -> tuple[list[Section], Usage, list[str]]:
    """One LLM call per category; any failure falls back to headlines for that category"""
    usage, sections, fallbacks = Usage(), [], []
    quota_gone = False
    for key, label in p.cfg.categories.items():
        arts = p.candidates.get(key)
        if not arts:
            continue
        try:
            if summarizer is None or quota_gone:
                raise LLMError("no summarizer available")
            stories, u = summarizer.summarize(label, arts, p.previous.get(key))
            usage.add(u)
            shown = [st for st in stories if st.status != "repeat"]
            dropped = [st for st in stories if st.status == "repeat"]
            for st in dropped:
                log.info("Dropped repeat in %s: %r (repeat of %r)", key, st.title, st.previous_title)
            sections.append(Section(key=key, label=label, stories=shown, dropped=dropped))
        except LLMError as exc:
            if isinstance(exc, QuotaExhausted):
                quota_gone = True   # don't burn time retrying the remaining categories
            if summarizer is not None and "no summarizer" not in str(exc):
                errors.append(f"summarize {key}: {exc}")
                log.warning("Summarizing %s failed, using headlines: %s", key, exc)
            fallbacks.append(key)
            sections.append(Section(key=key, label=label, headlines=arts[: s.max_per_category]))
    return sections, usage, fallbacks


def front_page(summarizer: Summarizer | None, sections: list[Section], recent_curiosities: list[str],
               errors: list[str]) -> tuple[Lead | None, Curiosity | None, Usage]:
    """Top story (moved out of its section) and the closing curiosity.
    Either can be missing: the digest is sent without it"""
    usage, lead, curiosity = Usage(), None, None
    if summarizer is None:
        return lead, curiosity, usage
    candidates = [(sec, i) for sec in sections for i in range(len(sec.stories))]
    if candidates:
        try:
            n, why, u = summarizer.pick_lead([(sec.label, sec.stories[i]) for sec, i in candidates])
            usage.add(u)
            sec, i = candidates[n]
            lead = Lead(key=sec.key, label=sec.label, story=sec.stories.pop(i), why_it_matters=why)
        except LLMError as exc:
            errors.append(f"top story: {exc}")
            log.warning("Picking the top story failed: %s", exc)
            if isinstance(exc, QuotaExhausted):
                return lead, curiosity, usage
    try:
        curiosity, u = summarizer.curiosity(recent_curiosities)
        usage.add(u)
    except LLMError as exc:
        errors.append(f"curiosity: {exc}")
        log.warning("Curiosity failed: %s", exc)
    return lead, curiosity, usage


def _summarizer_or_none(s: Settings) -> Summarizer | None:
    try:
        return make_summarizer(s)
    except LLMError as exc:
        log.warning("%s: every category will fall back to headlines", exc)
        return None


def run_digest(s: Settings, send: bool = True) -> RunResult:
    """send=False builds the digest (LLM calls included) without emailing or marking articles"""
    emailer = make_emailer(s) if send else None   # fail fast on bad email config
    summarizer = _summarizer_or_none(s)
    cap = summarizer.max_input if summarizer else s.max_per_category

    with db.connect(s.database_url) as conn:
        db.ensure_schema(conn)
        run_id = db.start_run(conn, "summary" if send else "preview")
        p = prepare(conn, s, cap)

    errors = list(p.errors)
    sections, usage, fallbacks = summarize_sections(summarizer, p, s, errors)
    lead, curiosity, front_usage = front_page(summarizer, sections, p.curiosities, errors)
    usage.add(front_usage)
    digest = build_summary_digest(sections, s.timezone, lead=lead, curiosity=curiosity)

    # The first connection would sit idle for minutes during the LLM phase and Neon suspends the
    # compute after ~5 min idle, killing it. Reconnect before sending: if the DB is down we fail before the email
    with db.connect(s.database_url) as conn:
        if send:
            emailer.send(digest.subject, digest.html, digest.text)
            db.save_digest(conn, "summary", digest.subject, digest.payload,
                           summarizer.label if summarizer else None,
                           usage.input_tokens, usage.output_tokens, fallbacks)
            # Everything in the window was considered; articles below the top-N cut were judged minor
            db.mark_sent(conn, [a["id"] for a in p.unsent])
        db.finish_run(conn, run_id, p.new_articles, len(p.unsent), errors)

    log.info("Digest built [%s]: %d articles considered, %d in / %d out tokens, fallbacks=%s",
             summarizer.label if summarizer else "no LLM", len(p.unsent),
             usage.input_tokens, usage.output_tokens, fallbacks or "none")
    return RunResult(digest, p.new_articles, len(p.unsent), usage, errors)
