import smtplib

import pytest

from app import emailer
from app.emailer import Emailer


class FakeSMTP:
    instances: list["FakeSMTP"] = []
    fail_times = 0
    auth_error = False

    def __init__(self, host, port, timeout):
        self.host, self.port, self.sent, self.tls, self.login_args = host, port, [], False, None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        if FakeSMTP.fail_times:
            FakeSMTP.fail_times -= 1
            raise OSError("connection refused")
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.tls = True

    def login(self, user, password):
        if FakeSMTP.auth_error:
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
        self.login_args = (user, password)

    def send_message(self, msg):
        self.sent.append(msg)


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch):
    FakeSMTP.instances, FakeSMTP.fail_times, FakeSMTP.auth_error = [], 0, False
    monkeypatch.setattr(emailer.smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


def make() -> Emailer:
    return Emailer("smtp.test", 587, "me@test", "pw", ["a@test", "b@test"])


@pytest.mark.parametrize("user, password, to, missing", [
    ("", "pw", ["a"], "SMTP_USER"),
    ("u", "", ["a"], "SMTP_PASSWORD"),
    ("u", "pw", [], "EMAIL_TO"),
])
def test_missing_settings(user, password, to, missing):
    with pytest.raises(RuntimeError, match=missing):
        Emailer("h", 587, user, password, to)


def test_send_builds_multipart_message():
    make().send("Subject ✓", "<p>Hi</p>", "Hi")
    [smtp] = FakeSMTP.instances
    assert smtp.tls and smtp.login_args == ("me@test", "pw")
    [msg] = smtp.sent
    assert msg["Subject"] == "Subject ✓"
    assert msg["To"] == "a@test, b@test"
    assert "me@test" in msg["From"]
    assert msg["Message-ID"]
    types = [p.get_content_type() for p in msg.walk()]
    assert "text/plain" in types and "text/html" in types
    assert msg.get_body(("plain",)).get_content().strip() == "Hi"
    assert "<p>Hi</p>" in msg.get_body(("html",)).get_content()


def test_send_retries_transient_failures():
    FakeSMTP.fail_times = 2
    make().send("s", "h", "t")
    assert len(FakeSMTP.instances) == 3
    assert len(FakeSMTP.instances[-1].sent) == 1


def test_send_gives_up_after_three_attempts():
    FakeSMTP.fail_times = 5
    with pytest.raises(OSError):
        make().send("s", "h", "t")
    assert len(FakeSMTP.instances) == 3


def test_auth_error_is_not_retried():
    FakeSMTP.auth_error = True
    with pytest.raises(RuntimeError, match="App Password"):
        make().send("s", "h", "t")
    assert len(FakeSMTP.instances) == 1
