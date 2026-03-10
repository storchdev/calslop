from __future__ import annotations

from email.message import EmailMessage
import os
import smtplib

from app.models.dtos import EmailSettings
from app.services.notifications.senders.base import NotificationSender


REQUIRED_EMAIL_ENV_VARS = (
    "CALSLOP_EMAIL_SMTP_HOST",
    "CALSLOP_EMAIL_SMTP_PORT",
    "CALSLOP_EMAIL_SMTP_USERNAME",
    "CALSLOP_EMAIL_SMTP_PASSWORD",
)


def missing_email_env_vars() -> list[str]:
    missing: list[str] = []
    for env_var in REQUIRED_EMAIL_ENV_VARS:
        if not os.environ.get(env_var):
            missing.append(env_var)
    return missing


class EmailSender(NotificationSender):
    def __init__(self, settings: EmailSettings):
        self._settings = settings

    def send(self, title: str, body: str) -> None:
        recipient = (self._settings.to or "").strip()
        if not recipient:
            raise ValueError("Email recipient is required")

        missing = missing_email_env_vars()
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing email environment variables: {joined}")

        smtp_host = os.environ["CALSLOP_EMAIL_SMTP_HOST"]
        smtp_port = int(os.environ["CALSLOP_EMAIL_SMTP_PORT"])
        smtp_username = os.environ["CALSLOP_EMAIL_SMTP_USERNAME"]
        smtp_password = os.environ["CALSLOP_EMAIL_SMTP_PASSWORD"]
        use_tls = os.environ.get("CALSLOP_EMAIL_USE_TLS", "1") == "1"
        from_addr = os.environ.get("CALSLOP_EMAIL_FROM") or smtp_username

        message = EmailMessage()
        message["Subject"] = title
        message["From"] = from_addr
        message["To"] = recipient
        message.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
            if use_tls:
                smtp.starttls()
            smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
