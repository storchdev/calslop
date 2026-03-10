from __future__ import annotations

from abc import ABC, abstractmethod


class NotificationSender(ABC):
    @abstractmethod
    def send(self, title: str, body: str) -> None:
        raise NotImplementedError
