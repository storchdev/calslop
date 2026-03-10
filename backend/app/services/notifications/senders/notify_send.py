from __future__ import annotations

import subprocess

from app.services.notifications.senders.base import NotificationSender


class NotifySendSender(NotificationSender):
    def send(self, title: str, body: str) -> None:
        subprocess.run(["notify-send", title, body], check=False)
