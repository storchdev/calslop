from __future__ import annotations

from string import Formatter

from app.models.dtos import NotificationSettings
from app.services.notifications.senders.base import NotificationSender
from app.services.notifications.senders.email import EmailSender, missing_email_env_vars
from app.services.notifications.senders.notify_send import NOTIFY_SEND_TIMEOUT_MS, NotifySendSender
from app.services.notifications.senders.webhook import WebhookSender

SUPPORTED_BODY_TEMPLATE_FIELDS = {"time", "delta", "title", "kind"}


def validate_notification_settings(settings: NotificationSettings) -> list[str]:
    errors: list[str] = []

    if settings.target == "webhook" and not (settings.webhook.url or "").strip():
        errors.append("Webhook URL is required for webhook notifications")

    if (
        settings.target == "notify_send"
        and settings.notify_send_timeout not in NOTIFY_SEND_TIMEOUT_MS
    ):
        errors.append("Invalid notify-send timeout value")

    if settings.target == "email":
        if not (settings.email.to or "").strip():
            errors.append("Email recipient is required for email notifications")
        missing = missing_email_env_vars()
        if missing:
            joined = ", ".join(missing)
            errors.append(f"Missing email environment variables: {joined}")

    template = settings.body_template or "{time}"
    try:
        for _, field_name, _, _ in Formatter().parse(template):
            if not field_name:
                continue
            if field_name not in SUPPORTED_BODY_TEMPLATE_FIELDS:
                allowed = ", ".join(sorted(SUPPORTED_BODY_TEMPLATE_FIELDS))
                errors.append(
                    f"Unsupported notification body template field '{field_name}'. Supported fields: {allowed}"
                )
                break
    except ValueError:
        errors.append("Notification body template contains invalid braces")

    return errors


def create_sender(settings: NotificationSettings) -> NotificationSender:
    errors = validate_notification_settings(settings)
    if errors:
        raise ValueError(errors[0])

    if settings.target == "notify_send":
        return NotifySendSender(settings.notify_send_timeout)
    if settings.target == "webhook":
        return WebhookSender(settings.webhook)
    if settings.target == "email":
        return EmailSender(settings.email)
    raise ValueError(f"Unsupported notification target: {settings.target}")
