from app.models.dtos import NotificationSettings
from app.services.notifications.senders.email import EmailSender
from app.services.notifications.senders.factory import create_sender, validate_notification_settings
from app.services.notifications.senders.notify_send import NotifySendSender
from app.services.notifications.senders.webhook import WebhookSender


def test_create_sender_notify_send():
    settings = NotificationSettings(enabled=True, target="notify_send")
    sender = create_sender(settings)
    assert isinstance(sender, NotifySendSender)


def test_create_sender_webhook():
    settings = NotificationSettings(
        enabled=True,
        target="webhook",
        webhook={"url": "https://example.com/hook", "headers": {"X-Test": "1"}},
    )
    sender = create_sender(settings)
    assert isinstance(sender, WebhookSender)


def test_create_sender_email_validates_env(monkeypatch):
    monkeypatch.delenv("CALSLOP_EMAIL_SMTP_HOST", raising=False)
    monkeypatch.delenv("CALSLOP_EMAIL_SMTP_PORT", raising=False)
    monkeypatch.delenv("CALSLOP_EMAIL_SMTP_USERNAME", raising=False)
    monkeypatch.delenv("CALSLOP_EMAIL_SMTP_PASSWORD", raising=False)
    settings = NotificationSettings(enabled=True, target="email", email={"to": "a@b.test"})

    errors = validate_notification_settings(settings)
    assert errors
    assert "CALSLOP_EMAIL_SMTP_HOST" in errors[0]


def test_create_sender_email(monkeypatch):
    monkeypatch.setenv("CALSLOP_EMAIL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("CALSLOP_EMAIL_SMTP_PORT", "587")
    monkeypatch.setenv("CALSLOP_EMAIL_SMTP_USERNAME", "user")
    monkeypatch.setenv("CALSLOP_EMAIL_SMTP_PASSWORD", "pass")
    settings = NotificationSettings(enabled=True, target="email", email={"to": "a@b.test"})
    sender = create_sender(settings)
    assert isinstance(sender, EmailSender)
