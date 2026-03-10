from __future__ import annotations

import httpx

from app.models.dtos import WebhookSettings
from app.services.notifications.senders.base import NotificationSender


class WebhookSender(NotificationSender):
    def __init__(self, settings: WebhookSettings):
        self._settings = settings

    def send(self, title: str, body: str) -> None:
        if not self._settings.url:
            raise ValueError("Webhook URL is required")
        response = httpx.post(
            self._settings.url,
            json={"title": title, "body": body},
            headers=self._settings.headers,
            timeout=10,
        )
        response.raise_for_status()
