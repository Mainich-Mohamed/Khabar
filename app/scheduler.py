"""Long-running process: fires the digest at DIGEST_HOURS in the configured timezone."""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from app.config import get_settings
from app.pipeline import make_emailer, run_digest

log = logging.getLogger(__name__)


def digest_job() -> None:
    s = get_settings()
    try:
        r = run_digest(s, send=True)
        log.info("Scheduled digest sent: %s", r.digest.subject)
    except Exception as exc:
        log.exception("Scheduled digest failed")
        try:
            make_emailer(s).send(
                "⚠️ news-digest run failed",
                f"<p>The scheduled digest failed:</p><pre>{type(exc).__name__}: {exc}</pre>"
                "<p>Check <code>docker compose logs scheduler</code>.</p>",
                f"The scheduled digest failed: {type(exc).__name__}: {exc}",
            )
        except Exception:
            log.exception("Could not send the failure notification either")


def start() -> None:
    s = get_settings()
    scheduler = BlockingScheduler(timezone=s.timezone)
    trigger = CronTrigger(hour=",".join(map(str, s.digest_hours)), minute=0, timezone=s.timezone)
    scheduler.add_job(
        digest_job, trigger, id="digest",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )
    next_runs, cursor = [], datetime.now(ZoneInfo(s.timezone))
    for _ in range(3):
        fire = trigger.get_next_fire_time(None, cursor)
        next_runs.append(f"{fire:%a %d %b %H:%M}")
        cursor = fire + timedelta(seconds=1)
    log.info("Scheduler started (%s). Next runs: %s", s.timezone, " | ".join(next_runs))
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped")