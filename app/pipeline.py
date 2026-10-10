"""The digest run: ingest -> select -> extract -> summarize -> email -> store"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app import db
from app.config import Settings, SourcesConfig, load_sources
from app.digest import Digest, Section, build_summary_digest
from app.emailer import Emailer
from app.extract import extract_leads
from app.ingest import ingest_all
from app.llm import LLMError, QuotaExhausted, Summarizer, Usage, make_summarizer

log = logging.getLogger(__name__)


@dataclass
class Prepared:
    cfg: SourcesConfig
    unsent: list[dict]                    # every unsent article in the window
    candidates: dict[str, list[dict]]     # category -> ranked articles (lead extracted)
    new_articles: int
    errors: list[str]


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
    return Prepared(cfg, unsent, candidates, new, errors)


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
            stories, u = summarizer.summarize(label, arts)
            usage.add(u)
            sections.append(Section(key=key, label=label, stories=stories))
        except LLMError as exc:
            if isinstance(exc, QuotaExhausted):
                quota_gone = True   # don't burn time retrying the remaining categories
            if summarizer is not None and "no summarizer" not in str(exc):
                errors.append(f"summarize {key}: {exc}")
                log.warning("Summarizing %s failed, using headlines: %s", key, exc)
            fallbacks.append(key)
            sections.append(Section(key=key, label=label, headlines=arts[: s.max_per_category]))
    return sections, usage, fallbacks


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
        digest = build_summary_digest(sections, s.timezone)

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
