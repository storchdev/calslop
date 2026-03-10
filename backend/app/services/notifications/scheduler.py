from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import threading
import time
from typing import Callable

from app.db.app_config_store import AppConfigStore
from app.db.sources_store import SourcesStore
from app.models.dtos import Event, NotificationSettings, Todo
from app.services.aggregator import aggregate_events_todos
from app.services.notifications.senders.factory import create_sender

LOGGER = logging.getLogger(__name__)
ALERT_LATE_GRACE_MS = 15_000


@dataclass(slots=True)
class ArmedAlert:
    key: str
    kind: str
    title: str
    dt: datetime
    minutes: int
    alert_at_ms: int
    ongoing_until_ms: int | None


def _dt_to_ms(value: datetime) -> int:
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return int(aware.timestamp() * 1000)


def _format_notification_time(value: datetime) -> str:
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.strftime("%b %d %H:%M UTC")


class NotificationScheduler:
    def __init__(
        self,
        *,
        sources_store: SourcesStore | None = None,
        config_store: AppConfigStore | None = None,
        poll_interval_seconds: float = 1.0,
        aggregate_fn: Callable = aggregate_events_todos,
    ):
        self._sources_store = sources_store or SourcesStore()
        self._config_store = config_store or AppConfigStore()
        self._poll_interval_seconds = poll_interval_seconds
        self._aggregate_fn = aggregate_fn
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._armed_alerts: list[ArmedAlert] = []
        self._notified_alerts: set[str] = set()
        self._last_notification_check_ms = int(time.time() * 1000)

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run, name="calslop-notifications", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def tick(self) -> None:
        raw = self._config_store.load()
        settings = NotificationSettings.model_validate(raw.get("notifications") or {})
        if not settings.enabled:
            self._armed_alerts = []
            self._notified_alerts.clear()
            self._last_notification_check_ms = int(time.time() * 1000)
            return

        sender = create_sender(settings)
        sources = self._sources_store.list_sources()
        events, todos, _ = self._aggregate_fn(sources)
        now_ms = int(time.time() * 1000)
        self._check_due_notifications(sender, now_ms)
        self._rebuild_armed_alerts(events, todos, now_ms)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception:
                LOGGER.exception("notification scheduler tick failed")
            self._stop_event.wait(self._poll_interval_seconds)

    def _rebuild_armed_alerts(
        self,
        events: list[Event],
        todos: list[Todo],
        now_ms: int,
    ) -> None:
        next_alerts: list[ArmedAlert] = []

        for event in events:
            if event.cancelled or not event.alert_minutes_before:
                continue
            start_ms = _dt_to_ms(event.start)
            end_ms = _dt_to_ms(event.end)

            for raw_minutes in event.alert_minutes_before:
                minutes = int(raw_minutes)
                if minutes < 0:
                    continue
                alert_at_ms = start_ms - (minutes * 60_000)
                if minutes == 0:
                    if end_ms <= now_ms:
                        continue
                elif alert_at_ms <= now_ms:
                    continue

                next_alerts.append(
                    ArmedAlert(
                        key=f"event:{event.id}:{event.start.isoformat()}:{minutes}",
                        kind="event",
                        title=event.title or "Event reminder",
                        dt=event.start,
                        minutes=minutes,
                        alert_at_ms=alert_at_ms,
                        ongoing_until_ms=end_ms if minutes == 0 else None,
                    )
                )

        for todo in todos:
            if todo.completed or not todo.due or not todo.alert_minutes_before:
                continue
            due_ms = _dt_to_ms(todo.due)

            for raw_minutes in todo.alert_minutes_before:
                minutes = int(raw_minutes)
                if minutes < 0:
                    continue
                alert_at_ms = due_ms - (minutes * 60_000)
                if alert_at_ms <= now_ms:
                    continue

                next_alerts.append(
                    ArmedAlert(
                        key=f"todo:{todo.id}:{todo.due.isoformat()}:{minutes}",
                        kind="todo",
                        title=todo.summary or "Todo reminder",
                        dt=todo.due,
                        minutes=minutes,
                        alert_at_ms=alert_at_ms,
                        ongoing_until_ms=None,
                    )
                )

        next_alerts.sort(key=lambda alert: alert.alert_at_ms)
        self._armed_alerts = next_alerts

        active_keys = {alert.key for alert in next_alerts}
        self._notified_alerts.intersection_update(active_keys)

    def _check_due_notifications(self, sender, now_ms: int) -> None:
        since = self._last_notification_check_ms
        self._last_notification_check_ms = now_ms

        remaining: list[ArmedAlert] = []
        for alert in self._armed_alerts:
            is_ongoing_at_time_event = (
                alert.kind == "event"
                and alert.minutes == 0
                and now_ms >= alert.alert_at_ms
                and alert.ongoing_until_ms is not None
                and now_ms < alert.ongoing_until_ms
            )

            is_fresh = now_ms - alert.alert_at_ms <= ALERT_LATE_GRACE_MS
            is_due_now = alert.alert_at_ms <= now_ms and alert.alert_at_ms > since and is_fresh
            should_notify = is_ongoing_at_time_event or is_due_now

            if should_notify and alert.key not in self._notified_alerts:
                self._notified_alerts.add(alert.key)
                body = _format_notification_time(alert.dt)
                if alert.minutes > 0:
                    body = f"{body} ({alert.minutes}m before)"
                try:
                    sender.send(alert.title, body)
                except Exception:
                    LOGGER.exception("failed to send notification")

            if is_ongoing_at_time_event or alert.alert_at_ms > now_ms:
                remaining.append(alert)

        self._armed_alerts = remaining
