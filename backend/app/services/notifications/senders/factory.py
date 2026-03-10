from __future__ import annotations

from app.models.dtos import NotificationSettings
from app.services.notifications.senders.base import NotificationSender
from app.services.notifications.senders.email import EmailSender, missing_email_env_vars
from app.services.notifications.senders.notify_send import NotifySendSender
from app.services.notifications.senders.webhook import WebhookSender


def validate_notification_settings(settings: NotificationSettings) -> list[str]:
    errors: list[str] = []

    if settings.target == "webhook" and not (settings.webhook.url or "").strip():
        errors.append("Webhook URL is required for webhook notifications")

    if settings.target == "email":
        if not (settings.email.to or "").strip():
            errors.append("Email recipient is required for email notifications")
        missing = missing_email_env_vars()
        if missing:
            joined = ", ".join(missing)
            errors.append(f"Missing email environment variables: {joined}")

    return errors


def create_sender(settings: NotificationSettings) -> NotificationSender:
    errors = validate_notification_settings(settings)
    if errors:
        raise ValueError(errors[0])

    if settings.target == "notify_send":
        return NotifySendSender()
    if settings.target == "webhook":
        return WebhookSender(settings.webhook)
    if settings.target == "email":
        return EmailSender(settings.email)
    raise ValueError(f"Unsupported notification target: {settings.target}")
