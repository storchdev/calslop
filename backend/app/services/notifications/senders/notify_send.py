from __future__ import annotations

import subprocess

from app.services.notifications.senders.base import NotificationSender

NOTIFY_SEND_TIMEOUT_MS = {
    "5s": 5000,
    "15s": 15000,
    "60s": 60000,
    "persistent": 0,
}


class NotifySendSender(NotificationSender):
    def __init__(self, timeout: str = "15s") -> None:
        self.timeout_ms = NOTIFY_SEND_TIMEOUT_MS.get(timeout, 15000)

    def send(self, title: str, body: str) -> None:
        subprocess.run(["notify-send", "-t", str(self.timeout_ms), title, body], check=False)
