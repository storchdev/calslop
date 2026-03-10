from app.models.dtos import EmailSettings, NotificationSettings, WebhookSettings
from app.services.notifications.senders.email import EmailSender
from app.services.notifications.senders.factory import create_sender, validate_notification_settings
from app.services.notifications.senders.notify_send import NotifySendSender
from app.services.notifications.senders.webhook import WebhookSender


def test_create_sender_notify_send():
    settings = NotificationSettings(enabled=True, target="notify_send", notify_send_timeout="60s")
    sender = create_sender(settings)
    assert isinstance(sender, NotifySendSender)
    assert sender.timeout_ms == 60000


def test_create_sender_webhook():
    settings = NotificationSettings(
        enabled=True,
        target="webhook",
        webhook=WebhookSettings(url="https://example.com/hook", headers={"X-Test": "1"}),
    )
    sender = create_sender(settings)
    assert isinstance(sender, WebhookSender)


def test_create_sender_email_validates_env(monkeypatch):
    monkeypatch.delenv("CALSLOP_EMAIL_SMTP_HOST", raising=False)
    monkeypatch.delenv("CALSLOP_EMAIL_SMTP_PORT", raising=False)
    monkeypatch.delenv("CALSLOP_EMAIL_SMTP_USERNAME", raising=False)
    monkeypatch.delenv("CALSLOP_EMAIL_SMTP_PASSWORD", raising=False)
    settings = NotificationSettings(
        enabled=True, target="email", email=EmailSettings(to="a@b.test")
    )

    errors = validate_notification_settings(settings)
    assert errors
    assert "CALSLOP_EMAIL_SMTP_HOST" in errors[0]


def test_create_sender_email(monkeypatch):
    monkeypatch.setenv("CALSLOP_EMAIL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("CALSLOP_EMAIL_SMTP_PORT", "587")
    monkeypatch.setenv("CALSLOP_EMAIL_SMTP_USERNAME", "user")
    monkeypatch.setenv("CALSLOP_EMAIL_SMTP_PASSWORD", "pass")
    settings = NotificationSettings(
        enabled=True, target="email", email=EmailSettings(to="a@b.test")
    )
    sender = create_sender(settings)
    assert isinstance(sender, EmailSender)


def test_validate_notification_template_rejects_unknown_field():
    settings = NotificationSettings(
        enabled=True,
        target="notify_send",
        body_template="{time}\n{unknown_field}",
    )
    errors = validate_notification_settings(settings)
    assert errors
    assert "Unsupported notification body template field" in errors[0]


def test_validate_notification_settings_rejects_invalid_notify_send_timeout():
    settings = NotificationSettings(enabled=True, target="notify_send")
    settings.notify_send_timeout = "never"  # type: ignore[assignment]

    errors = validate_notification_settings(settings)
    assert errors
    assert "Invalid notify-send timeout value" in errors[0]
