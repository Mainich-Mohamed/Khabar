"""news-digest CLI

  check-feeds     test every feed in sources.yaml (no DB, no email)
  send-test       send a test email to EMAIL_TO
  ingest          fetch feeds and store new articles
  preview         build the AI digest into preview.html (calls the LLM, sends nothing, marks nothing)
  run             ingest + summarize + email the digest (what the scheduler calls)
  run-headlines   Step 1 behaviour: email raw headlines, no LLM
  scheduler       stay running and send the digest at DIGEST_HOURS
  llm-test        one tiny Gemini request: is the key/model right?
"""
import argparse
import logging
import sys

from app import db
from app.config import get_settings, load_sources
from app.digest import build_headlines
from app.ingest import fetch_feed, ingest_all, make_client
from app.llm import LLMError, make_summarizer
from app.pipeline import make_emailer, run_digest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)          # one line per request is too noisy
logging.getLogger("trafilatura").setLevel(logging.ERROR)
log = logging.getLogger("news-digest")


def cmd_check_feeds(s) -> int:
    cfg = load_sources(s.sources_path)
    failed = 0
    with make_client() as client:
        for src in cfg.sources:
            try:
                n = len(fetch_feed(client, src))
                failed += n == 0
                print(f"{'OK   ' if n else 'EMPTY'} {src.name:<24} {n:>3} items   [{src.category}]")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"FAIL  {src.name:<24} {type(exc).__name__}: {exc}")
    print(f"\n{len(cfg.sources) - failed}/{len(cfg.sources)} feeds working")
    return 1 if failed else 0


def cmd_send_test(s) -> int:
    make_emailer(s).send(
        "✅ news-digest is connected",
        "<p>Email delivery works.</p>",
        "Email delivery works.",
    )
    print("Sent. Check your inbox (and spam folder the first time).")
    return 0


def cmd_ingest(s) -> int:
    cfg = load_sources(s.sources_path)
    with db.connect(s.database_url) as conn:
        db.ensure_schema(conn)
        new, errors = ingest_all(conn, cfg.sources, db.insert_article)
    log.info("Ingest done: %d new articles, %d failed feeds", new, len(errors))
    return 0


def cmd_preview(s) -> int:
    r = run_digest(s, send=False)
    with open("preview.html", "w", encoding="utf-8") as f:
        f.write(r.digest.html)
    print(f"\nSubject: {r.digest.subject}")
    print(f"Wrote preview.html — {r.considered} articles considered, "
          f"{r.usage.input_tokens} in / {r.usage.output_tokens} out tokens. Nothing sent or marked.")
    return 0


def cmd_run(s) -> int:
    r = run_digest(s, send=True)
    print(f"Sent: {r.digest.subject}")
    return 0


def cmd_run_headlines(s) -> int:
    cfg = load_sources(s.sources_path)
    emailer = make_emailer(s)
    with db.connect(s.database_url) as conn:
        db.ensure_schema(conn)
        run_id = db.start_run(conn, "headlines")
        new, errors = ingest_all(conn, cfg.sources, db.insert_article)
        rows = db.fetch_unsent(conn, s.max_per_category)
        d = build_headlines(rows, cfg.categories, s.timezone)
        emailer.send(d.subject, d.html, d.text)
        db.mark_sent(conn, [r["id"] for r in rows])
        db.finish_run(conn, run_id, new, len(rows), errors)
    print(f"Sent: {d.subject}")
    return 0


def cmd_llm_test(s) -> int:
    from datetime import datetime, timezone
    article = {"id": 0, "source": "Test Wire", "url": "https://example.com/test",
               "title": "City council approves new public library",
               "summary": "The council voted 7-2 on Monday to fund a new central library, due to open in 2028.",
               "lead": None, "published_at": datetime.now(timezone.utc)}
    try:
        z = make_summarizer(s)
        stories, usage = z.summarize("Test", [article])
    except LLMError as exc:
        print(f"FAILED   {s.gemini_model}: {exc}")
        return 1
    print(f"OK       {z.label}  ({usage.input_tokens} in / {usage.output_tokens} out tokens)")
    print(f"         {stories[0].title}")
    return 0


def main() -> int:
    commands = {
        "check-feeds": cmd_check_feeds,
        "send-test": cmd_send_test,
        "ingest": cmd_ingest,
        "preview": cmd_preview,
        "run": cmd_run,
        "run-headlines": cmd_run_headlines,
        "llm-test": cmd_llm_test,
    }
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=[*commands, "scheduler"])
    args = parser.parse_args()

    if args.command == "scheduler":
        from app.scheduler import start
        start()
        return 0
    return commands[args.command](get_settings())


if __name__ == "__main__":
    sys.exit(main())