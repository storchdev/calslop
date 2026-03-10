from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timezone
from typing import Any

from dateutil.rrule import rrulestr


def to_naive_utc(dt: datetime | date | None) -> datetime | None:
    if dt is None:
        return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return datetime.combine(dt, datetime.min.time())
    if getattr(dt, "tzinfo", None):
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def recurrence_id_str(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def recurrence_id_keys(dt: datetime) -> tuple[str, str]:
    dt_utc = to_naive_utc(dt) or dt
    return recurrence_id_str(dt_utc), dt_utc.strftime("%Y%m%d")


def normalize_rrule(rrule_value) -> str | None:
    if rrule_value is None:
        return None
    if hasattr(rrule_value, "to_ical"):
        text = rrule_value.to_ical().decode()
    else:
        text = str(rrule_value)
    text = text.strip().replace("\r\n", "\n").replace("\r", "\n")
    return text or None


def parse_rrule(rrule_value, dtstart: datetime | None):
    normalized = normalize_rrule(rrule_value)
    if not normalized or dtstart is None:
        return None
    dtstart_value = dtstart if dtstart.tzinfo else dtstart.replace(tzinfo=timezone.utc)
    try:
        return rrulestr(normalized, dtstart=dtstart_value)
    except Exception:
        return None


def iter_occurrences_in_window(rule, start: datetime | None, end: datetime | None) -> Iterable[datetime]:
    if start is None or end is None:
        return []
    start_value = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    end_value = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
    try:
        return rule.between(start_value, end_value, inc=True)
    except Exception:
        return []


def parse_iso_window(start: str | None, end: str | None) -> tuple[datetime | None, datetime | None]:
    if not start or not end:
        return None, None
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None, None
    return to_naive_utc(start_dt), to_naive_utc(end_dt)


def merge_exception_component(
    index: dict[str, tuple[Any, int]], key: str, component: Any, cancelled: bool
) -> None:
    rank = 2 if cancelled else 1
    existing = index.get(key)
    if existing is None or rank >= existing[1]:
        index[key] = (component, rank)
