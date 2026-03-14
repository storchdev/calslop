from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import logging
import os
import threading
import time
import heapq
import json
from typing import Callable

from app.db.app_config_store import AppConfigStore
from app.db.sources_store import SourcesStore
from app.models.dtos import Event, NotificationSettings, Todo
from app.services.aggregator import aggregate_events_todos
from app.services.notifications.senders.factory import create_sender

LOGGER = logging.getLogger(__name__)
ALERT_LATE_GRACE_MS = 15_000
DEFAULT_NOTIFICATION_TIME_FORMAT = "%b %d %H:%M %Z"
DEFAULT_NOTIFICATION_BODY_TEMPLATE = "{time}"
SCHEDULER_WINDOW_LOOKBACK_DAYS = 1
SCHEDULER_WINDOW_LOOKAHEAD_DAYS = 365


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
    local_dt = aware.astimezone()
    return local_dt.strftime(DEFAULT_NOTIFICATION_TIME_FORMAT)


def _format_notification_time_with_format(value: datetime, time_format: str) -> str:
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    local_dt = aware.astimezone()
    return local_dt.strftime(time_format)


def _human_relative_delta(now_ms: int, target: datetime) -> str:
    delta_seconds = int(round((_dt_to_ms(target) - now_ms) / 1000))
    if abs(delta_seconds) < 30:
        return "now"

    remaining = abs(delta_seconds)
    chunks: list[str] = []
    for unit_seconds, unit_label in ((86_400, "d"), (3_600, "h"), (60, "m"), (1, "s")):
        if remaining < unit_seconds:
            continue
        value, remaining = divmod(remaining, unit_seconds)
        chunks.append(f"{value}{unit_label}")
        if len(chunks) == 2:
            break

    if not chunks:
        chunks = ["0m"]

    text = " ".join(chunks)
    if delta_seconds > 0:
        return f"in {text}"
    return f"{text} ago"


def render_notification_body(
    *,
    title: str,
    kind: str,
    target_dt: datetime,
    now_ms: int,
    time_format: str,
    body_template: str,
) -> str:
    format_value = time_format or DEFAULT_NOTIFICATION_TIME_FORMAT
    template_value = body_template or DEFAULT_NOTIFICATION_BODY_TEMPLATE
    values = {
        "title": title,
        "kind": kind,
        "time": _format_notification_time_with_format(target_dt, format_value),
        "delta": _human_relative_delta(now_ms, target_dt),
    }
    return template_value.format_map(values)


class NotificationScheduler:
    def __init__(
        self,
        *,
        sources_store: SourcesStore | None = None,
        config_store: AppConfigStore | None = None,
        poll_interval_seconds: float = 1.0,
        refresh_interval_seconds: float | None = None,
        aggregate_fn: Callable = aggregate_events_todos,
    ):
        self._sources_store = sources_store or SourcesStore()
        self._config_store = config_store or AppConfigStore()
        self._poll_interval_seconds = poll_interval_seconds
        env_refresh_seconds = os.environ.get("CALSLOP_NOTIFICATION_REFRESH_SECONDS")
        if refresh_interval_seconds is not None:
            resolved_refresh_seconds = refresh_interval_seconds
        elif env_refresh_seconds is not None:
            try:
                resolved_refresh_seconds = float(env_refresh_seconds)
            except ValueError:
                LOGGER.warning(
                    "invalid CALSLOP_NOTIFICATION_REFRESH_SECONDS=%r, using default",
                    env_refresh_seconds,
                )
                resolved_refresh_seconds = 60.0
        else:
            resolved_refresh_seconds = 60.0
        self._refresh_interval_seconds = max(1.0, resolved_refresh_seconds)
        self._aggregate_fn = aggregate_fn
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._armed_alerts: list[ArmedAlert] = []
        self._alert_heap: list[tuple[int, int, ArmedAlert]] = []
        self._heap_counter = 0
        self._notified_alerts: set[str] = set()
        now_ms = int(time.time() * 1000)
        self._last_notification_check_ms = now_ms
        self._snapshot_events: list[Event] = []
        self._snapshot_todos: list[Todo] = []
        self._next_refresh_ms = now_ms
        self._last_settings_fingerprint: str | None = None
        self._last_sources_fingerprint: str | None = None
        self._force_refresh = False
        self._refresh_count = 0
        self._refresh_skipped_unchanged = 0

    def request_refresh(self) -> None:
        self._force_refresh = True

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

    def tick(self) -> float:
        raw = self._config_store.load()
        settings = NotificationSettings.model_validate(raw.get("notifications") or {})
        now_ms = int(time.time() * 1000)
        settings_fingerprint = self._fingerprint_settings(settings)
        settings_changed = settings_fingerprint != self._last_settings_fingerprint
        self._last_settings_fingerprint = settings_fingerprint

        if not settings.enabled:
            self._armed_alerts = []
            self._alert_heap = []
            self._snapshot_events = []
            self._snapshot_todos = []
            self._next_refresh_ms = now_ms
            self._notified_alerts.clear()
            self._last_notification_check_ms = now_ms
            self._last_sources_fingerprint = None
            self._force_refresh = False
            return self._poll_interval_seconds

        sender = create_sender(settings)
        should_refresh = self._force_refresh or settings_changed or now_ms >= self._next_refresh_ms
        if should_refresh:
            refresh_started = time.perf_counter()
            sources = self._sources_store.list_sources()
            window_start_iso, window_end_iso = self._build_refresh_window_iso(now_ms)
            try:
                events, todos, _ = self._aggregate_fn(
                    sources,
                    start=window_start_iso,
                    end=window_end_iso,
                )
            except TypeError:
                # Backward compatibility for injected aggregate fns in tests.
                events, todos, _ = self._aggregate_fn(sources)
            self._snapshot_events = events
            self._snapshot_todos = todos
            fingerprint = self._fingerprint_snapshot(events, todos)
            refresh_duration_ms = int((time.perf_counter() - refresh_started) * 1000)
            if fingerprint != self._last_sources_fingerprint:
                self._rebuild_armed_alerts(events, todos, now_ms)
                self._last_sources_fingerprint = fingerprint
                LOGGER.debug(
                    "notifications refresh rebuilt alerts count=%d duration_ms=%d refresh_count=%d",
                    len(self._armed_alerts),
                    refresh_duration_ms,
                    self._refresh_count + 1,
                )
            else:
                self._refresh_skipped_unchanged += 1
                LOGGER.debug(
                    "notifications refresh unchanged duration_ms=%d skipped_unchanged=%d",
                    refresh_duration_ms,
                    self._refresh_skipped_unchanged,
                )
            self._refresh_count += 1
            self._next_refresh_ms = now_ms + int(self._refresh_interval_seconds * 1000)
            self._force_refresh = False

        sent_count = self._check_due_notifications(sender, settings, now_ms)
        if sent_count:
            LOGGER.debug("notifications dispatch sent_count=%d", sent_count)
        return self._compute_wait_seconds(now_ms)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            wait_seconds = self._poll_interval_seconds
            try:
                wait_seconds = self.tick()
            except Exception:
                LOGGER.exception("notification scheduler tick failed")
            self._stop_event.wait(wait_seconds)

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
        self._alert_heap = []
        for alert in next_alerts:
            heapq.heappush(self._alert_heap, (alert.alert_at_ms, self._heap_counter, alert))
            self._heap_counter += 1

        active_keys = {alert.key for alert in next_alerts}
        self._notified_alerts.intersection_update(active_keys)

    def _check_due_notifications(self, sender, settings: NotificationSettings, now_ms: int) -> int:
        since = self._last_notification_check_ms
        self._last_notification_check_ms = now_ms
        sent_count = 0

        while self._alert_heap and self._alert_heap[0][0] <= now_ms:
            _, _, alert = heapq.heappop(self._alert_heap)
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
                body = render_notification_body(
                    title=alert.title,
                    kind=alert.kind,
                    target_dt=alert.dt,
                    now_ms=now_ms,
                    time_format=settings.time_format,
                    body_template=settings.body_template,
                )
                try:
                    sender.send(alert.title, body)
                    sent_count += 1
                except Exception:
                    LOGGER.exception("failed to send notification")

        self._armed_alerts = [
            item[2] for item in sorted(self._alert_heap, key=lambda item: item[0])
        ]
        return sent_count

    def _build_refresh_window_iso(self, now_ms: int) -> tuple[str, str]:
        now_dt = datetime.fromtimestamp(now_ms / 1000, tz=UTC)
        window_start = now_dt - timedelta(days=SCHEDULER_WINDOW_LOOKBACK_DAYS)
        window_end = now_dt + timedelta(days=SCHEDULER_WINDOW_LOOKAHEAD_DAYS)
        return window_start.isoformat().replace("+00:00", "Z"), window_end.isoformat().replace(
            "+00:00", "Z"
        )

    def _compute_wait_seconds(self, now_ms: int) -> float:
        refresh_due_ms = max(0, self._next_refresh_ms - now_ms)
        if self._alert_heap:
            dispatch_due_ms = max(0, self._alert_heap[0][0] - now_ms)
            near_term_cap_ms = int(self._poll_interval_seconds * 1000)
            if dispatch_due_ms <= near_term_cap_ms:
                return self._poll_interval_seconds
            wait_ms = min(dispatch_due_ms, refresh_due_ms)
            return max(0.05, wait_ms / 1000)
        if refresh_due_ms <= 0:
            return 0.05
        return max(self._poll_interval_seconds, refresh_due_ms / 1000)

    def _fingerprint_settings(self, settings: NotificationSettings) -> str:
        payload = settings.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha1(encoded).hexdigest()

    def _fingerprint_snapshot(self, events: list[Event], todos: list[Todo]) -> str:
        event_keys = sorted(
            (
                event.id,
                event.start.isoformat(),
                event.end.isoformat(),
                event.cancelled,
                tuple(event.alert_minutes_before or []),
                event.title,
            )
            for event in events
        )
        todo_keys = sorted(
            (
                todo.id,
                todo.due.isoformat() if todo.due else "",
                todo.completed,
                tuple(todo.alert_minutes_before or []),
                todo.summary,
            )
            for todo in todos
        )
        encoded = json.dumps(
            {"events": event_keys, "todos": todo_keys},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha1(encoded).hexdigest()
