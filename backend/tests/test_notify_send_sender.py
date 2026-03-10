import pytest

from app.services.notifications.senders.notify_send import NotifySendSender


@pytest.mark.parametrize(
    ("timeout", "expected_ms"),
    [
        ("5s", 5000),
        ("15s", 15000),
        ("60s", 60000),
        ("persistent", 0),
    ],
)
def test_notify_send_sender_uses_timeout_flag(monkeypatch, timeout, expected_ms):
    calls: list[tuple[list[str], bool]] = []

    def fake_run(command: list[str], check: bool = False) -> None:
        calls.append((command, check))

    monkeypatch.setattr("app.services.notifications.senders.notify_send.subprocess.run", fake_run)

    sender = NotifySendSender(timeout)
    sender.send("Title", "Body")

    assert calls == [(["notify-send", "-t", str(expected_ms), "Title", "Body"], False)]
