import logging
import smtplib
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

log = logging.getLogger(__name__)


class Emailer:
    def __init__(self, host: str, port: int, user: str, password: str, to: list[str]):
        missing = [n for n, v in {"SMTP_USER": user, "SMTP_PASSWORD": password, "EMAIL_TO": to}.items() if not v]
        if missing:
            raise RuntimeError(f"Missing email settings in .env: {', '.join(missing)}")
        self.host, self.port, self.user, self.password, self.to = host, port, user, password, to

    def send(self, subject: str, html: str, text: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"News Digest <{self.user}>"
        msg["To"] = ", ".join(self.to)
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="news-digest.local")
        msg.set_content(text)                 # plain-text fallback
        msg.add_alternative(html, subtype="html")

        for attempt in range(1, 4):
            try:
                with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
                    smtp.starttls()
                    smtp.login(self.user, self.password)
                    smtp.send_message(msg)
                log.info("Email sent to %s: %s", msg["To"], subject)
                return
            except smtplib.SMTPAuthenticationError as exc:
                # Retrying won't fix bad credentials
                raise RuntimeError(
                    "Gmail rejected the login. Use an App Password (2-Step Verification must be ON), "
                    "not your normal password."
                ) from exc
            except (smtplib.SMTPException, OSError) as exc:
                log.warning("Send attempt %d failed: %s", attempt, exc)
                if attempt == 3:
                    raise
                time.sleep(5 * attempt)
