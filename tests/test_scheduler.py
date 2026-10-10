from types import SimpleNamespace

from app import scheduler


def test_digest_job_success_sends_no_alert(monkeypatch, settings):
    alerts = []
    monkeypatch.setattr(scheduler, "get_settings", lambda: settings)
    monkeypatch.setattr(scheduler, "run_digest",
                        lambda s, send: SimpleNamespace(digest=SimpleNamespace(subject="ok")))
    monkeypatch.setattr(scheduler, "make_emailer", lambda s: SimpleNamespace(send=lambda *a: alerts.append(a)))
    scheduler.digest_job()
    assert alerts == []


def test_digest_job_failure_sends_alert(monkeypatch, settings):
    alerts = []

    def boom(s, send):
        raise ConnectionError("db down <b>")

    monkeypatch.setattr(scheduler, "get_settings", lambda: settings)
    monkeypatch.setattr(scheduler, "run_digest", boom)
    monkeypatch.setattr(scheduler, "make_emailer", lambda s: SimpleNamespace(send=lambda *a: alerts.append(a)))
    scheduler.digest_job()
    [(subject, html, text)] = alerts
    assert "failed" in subject
    assert "ConnectionError: db down" in text


def test_digest_job_never_raises_even_if_alert_fails(monkeypatch, settings):
    def boom(*a, **kw):
        raise RuntimeError("everything is broken")

    monkeypatch.setattr(scheduler, "get_settings", lambda: settings)
    monkeypatch.setattr(scheduler, "run_digest", boom)
    monkeypatch.setattr(scheduler, "make_emailer", boom)
    scheduler.digest_job()   # must not propagate: an exception here would kill the job
