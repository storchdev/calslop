"""Parse icalendar components into Event/Todo DTOs."""

from functools import lru_cache
import os
from pathlib import Path
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import icalendar
from icalendar import vRecur
from dateutil.rrule import rrulestr

from app.models.dtos import Event, Todo
from app.services.ical_recurrence import (
    iter_occurrences_in_window,
    merge_exception_component,
    normalize_rrule,
    next_occurrence_on_or_after,
    next_occurrence_strictly_after,
    parse_rrule,
    recurrence_id_keys,
    recurrence_id_str,
    to_naive_utc,
)


def _to_naive_utc(dt: datetime | date | None) -> datetime | None:
    return to_naive_utc(dt)


def _to_aware_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@lru_cache(maxsize=1)
def _local_timezone():
    tz_name = os.environ.get("TZ", "").strip()
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            pass

    timezone_file = Path("/etc/timezone")
    if timezone_file.exists():
        try:
            name = timezone_file.read_text(encoding="utf-8").strip()
            if name:
                return ZoneInfo(name)
        except Exception:
            pass

    localtime_path = Path("/etc/localtime")
    try:
        if localtime_path.exists() and localtime_path.is_symlink():
            target = localtime_path.resolve()
            marker = "/zoneinfo/"
            target_str = str(target)
            if marker in target_str:
                name = target_str.split(marker, 1)[1]
                if name:
                    return ZoneInfo(name)
    except Exception:
        pass

    local_tz = datetime.now().astimezone().tzinfo
    return local_tz or timezone.utc


def _to_aware_local(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    local_tz = _local_timezone()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(local_tz)


def _get_dt(component: Any, key: str) -> datetime | None:
    return _get_dt_for_output(component, key)


def _get_dt_for_output(component: Any, key: str) -> datetime | None:
    val = component.get(key)
    if val is None:
        return None
    if hasattr(val, "dts"):
        dts = val.dts if hasattr(val.dts, "__iter__") else [val.dts]
        for d in dts:
            if d and getattr(d, "dt", None):
                return _to_naive_utc(d.dt)
        return None
    if hasattr(val, "dt"):
        return _to_naive_utc(val.dt)
    return None


def _get_dt_for_recurrence(component: Any, key: str) -> datetime | None:
    val = component.get(key)
    if val is None:
        return None
    if hasattr(val, "dts"):
        dts = val.dts if hasattr(val.dts, "__iter__") else [val.dts]
        for d in dts:
            dt_value = getattr(d, "dt", None) if d else None
            if isinstance(dt_value, datetime):
                return dt_value
            if isinstance(dt_value, date):
                return datetime.combine(dt_value, datetime.min.time())
        return None
    dt_value = getattr(val, "dt", None)
    if isinstance(dt_value, datetime):
        return dt_value
    if isinstance(dt_value, date):
        return datetime.combine(dt_value, datetime.min.time())
    return None


def _is_all_day(component: Any) -> bool:
    dtstart = component.get("dtstart")
    if dtstart is None:
        return False
    dt = getattr(dtstart, "dt", None)
    return isinstance(dt, date) and not isinstance(dt, datetime)


def _extract_alarm_minutes_before(
    component: Any,
    reference_dt: datetime | None,
) -> list[int] | None:
    """Extract minutes-before reminders from DISPLAY VALARM triggers."""
    if not reference_dt:
        return None
    values: set[int] = set()
    for sub in list(getattr(component, "subcomponents", []) or []):
        if getattr(sub, "name", "") != "VALARM":
            continue
        action = str(sub.get("action", "")).upper()
        if action and action != "DISPLAY":
            continue
        trigger = sub.get("trigger")
        if trigger is None:
            continue

        try:
            # Relative trigger (e.g. -PT15M)
            trigger_td = getattr(trigger, "td", None)
            if isinstance(trigger_td, timedelta):
                delta_seconds = trigger_td.total_seconds()
                if delta_seconds <= 0:
                    values.add(int(round(abs(delta_seconds) / 60)))
                continue

            # Some icalendar objects expose timedelta as .dt as well.
            trigger_dt = getattr(trigger, "dt", None)
            if isinstance(trigger_dt, timedelta):
                delta_seconds = trigger_dt.total_seconds()
                if delta_seconds <= 0:
                    values.add(int(round(abs(delta_seconds) / 60)))
                continue

            # Absolute trigger datetime
            if trigger_dt is not None:
                trigger_as_dt = _to_naive_utc(trigger_dt)
                if isinstance(trigger_as_dt, datetime):
                    delta_seconds = (reference_dt - trigger_as_dt).total_seconds()
                    if delta_seconds >= 0:
                        values.add(int(round(delta_seconds / 60)))
        except Exception:
            # Ignore malformed alarm trigger values.
            continue
    if not values:
        return None
    return sorted(values)


def _set_display_alarm(component: Any, minutes_before: list[int] | None) -> None:
    """Replace VALARM entries with DISPLAY alarms at minutes-before values."""
    if getattr(component, "subcomponents", None):
        component.subcomponents = [
            sub for sub in list(component.subcomponents) if getattr(sub, "name", "") != "VALARM"
        ]
    if not minutes_before:
        return
    for mins in sorted({max(0, int(m)) for m in minutes_before}):
        alarm = icalendar.Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", "Reminder")
        alarm.add("trigger", -timedelta(minutes=mins))
        component.add_component(alarm)


def _event_intersects_window(
    start: datetime,
    end: datetime,
    window_start: datetime | None,
    window_end: datetime | None,
) -> bool:
    if window_start is None or window_end is None:
        return True
    return end >= window_start and start <= window_end


def _event_text(component: Any, key: str) -> str | None:
    value = component.get(key)
    return str(value) if value is not None else None


def _event_cancelled(component: Any) -> bool:
    return (component.get("status") or "").upper() == "CANCELLED"


def _collect_exdate_keys(component: Any) -> set[str]:
    keys: set[str] = set()
    exdate_val = component.get("exdate")
    if exdate_val is None:
        return keys
    exdates = exdate_val if isinstance(exdate_val, list) else [exdate_val]
    for item in exdates:
        dts = list(getattr(item, "dts", []) or [])
        for dt_entry in dts:
            dt_value = to_naive_utc(getattr(dt_entry, "dt", None))
            if not isinstance(dt_value, datetime):
                continue
            dt_key, date_key = recurrence_id_keys(dt_value)
            keys.add(dt_key)
            keys.add(date_key)
    return keys


def _build_event(
    *,
    source_id: str,
    uid: str,
    recurrence_id: str | None,
    title: str,
    start: datetime,
    end: datetime,
    all_day: bool,
    description: str | None,
    recurrence: str | None,
    location: str | None,
    url: str | None,
    alert_minutes_before: list[int] | None,
    cancelled: bool,
) -> Event:
    event_id = f"{source_id}::{uid}::{recurrence_id}" if recurrence_id else f"{source_id}::{uid}"
    return Event(
        id=event_id,
        source_id=source_id,
        title=title,
        start=start,
        end=end,
        all_day=all_day,
        description=description,
        recurrence=recurrence,
        location=location,
        url=url,
        alert_minutes_before=alert_minutes_before,
        cancelled=cancelled,
    )


def parse_events_from_ical(
    ical_text: str | bytes,
    source_id: str,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> list[Event]:
    """Parse VCALENDAR/VEVENT from .ics content. Returns list of Event DTOs."""
    if isinstance(ical_text, str):
        ical_text = ical_text.encode("utf-8")
    cal = icalendar.Calendar.from_ical(ical_text)
    if not cal:
        return []
    by_uid: dict[str, list[Any]] = {}
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        uid = str(component.get("uid", ""))
        if not uid:
            continue
        by_uid.setdefault(uid, []).append(component)

    events: list[Event] = []
    for uid, components in by_uid.items():
        masters = [c for c in components if _recurrence_id_from_component(c) is None]
        exceptions = [c for c in components if _recurrence_id_from_component(c) is not None]

        exception_index: dict[str, tuple[Any, int]] = {}
        for component in exceptions:
            rec_dt = _recurrence_id_from_component(component)
            if rec_dt is None:
                continue
            dt_key, date_key = recurrence_id_keys(rec_dt)
            merge_exception_component(
                exception_index, dt_key, component, _event_cancelled(component)
            )
            merge_exception_component(
                exception_index, date_key, component, _event_cancelled(component)
            )

        for master in masters:
            start = _get_dt_for_output(master, "dtstart")
            end = _get_dt_for_output(master, "dtend")
            if not start:
                continue
            if not end:
                end = start
            summary = str(master.get("summary", "Untitled"))
            description = _event_text(master, "description")
            location = _event_text(master, "location")
            url = _event_text(master, "url")
            recurrence = normalize_rrule(master.get("rrule"))
            all_day = _is_all_day(master)
            cancelled = _event_cancelled(master)

            if not recurrence:
                if _event_intersects_window(start, end, window_start, window_end):
                    events.append(
                        _build_event(
                            source_id=source_id,
                            uid=uid,
                            recurrence_id=None,
                            title=summary,
                            start=start,
                            end=end,
                            all_day=all_day,
                            description=description,
                            recurrence=None,
                            location=location,
                            url=url,
                            alert_minutes_before=_extract_alarm_minutes_before(master, start),
                            cancelled=cancelled,
                        )
                    )
                continue

            recurrence_start = _get_dt_for_recurrence(master, "dtstart")
            recurrence_end = _get_dt_for_recurrence(master, "dtend")
            if not recurrence_start:
                recurrence_start = start
            if not recurrence_end:
                recurrence_end = recurrence_start

            rule = parse_rrule(recurrence, recurrence_start)
            if rule is None or window_start is None or window_end is None:
                if _event_intersects_window(start, end, window_start, window_end):
                    events.append(
                        _build_event(
                            source_id=source_id,
                            uid=uid,
                            recurrence_id=None,
                            title=summary,
                            start=start,
                            end=end,
                            all_day=all_day,
                            description=description,
                            recurrence=recurrence,
                            location=location,
                            url=url,
                            alert_minutes_before=_extract_alarm_minutes_before(master, start),
                            cancelled=cancelled,
                        )
                    )
                continue

            duration = recurrence_end - recurrence_start
            exdate_keys = _collect_exdate_keys(master)
            for occurrence in iter_occurrences_in_window(rule, window_start, window_end):
                occ_start = to_naive_utc(occurrence)
                if not isinstance(occ_start, datetime):
                    continue
                rec_key, rec_date_key = recurrence_id_keys(occ_start)
                if rec_key in exdate_keys or rec_date_key in exdate_keys:
                    continue

                exc = exception_index.get(rec_key) or exception_index.get(rec_date_key)
                if exc is not None:
                    exc_component = exc[0]
                    if _event_cancelled(exc_component):
                        continue
                    exc_start = _get_dt(exc_component, "dtstart") or occ_start
                    exc_end = _get_dt(exc_component, "dtend") or (exc_start + duration)
                    exc_summary = str(exc_component.get("summary", summary))
                    exc_description = _event_text(exc_component, "description")
                    exc_location = _event_text(exc_component, "location")
                    exc_url = _event_text(exc_component, "url")
                    rec_override = _recurrence_id_from_component(exc_component)
                    rec_id = recurrence_id_str(rec_override) if rec_override else rec_key
                    events.append(
                        _build_event(
                            source_id=source_id,
                            uid=uid,
                            recurrence_id=rec_id,
                            title=exc_summary,
                            start=exc_start,
                            end=exc_end,
                            all_day=_is_all_day(exc_component),
                            description=exc_description
                            if exc_description is not None
                            else description,
                            recurrence=recurrence,
                            location=exc_location if exc_location is not None else location,
                            url=exc_url if exc_url is not None else url,
                            alert_minutes_before=_extract_alarm_minutes_before(
                                exc_component, exc_start
                            )
                            or _extract_alarm_minutes_before(master, start),
                            cancelled=False,
                        )
                    )
                    continue

                events.append(
                    _build_event(
                        source_id=source_id,
                        uid=uid,
                        recurrence_id=rec_key,
                        title=summary,
                        start=occ_start,
                        end=occ_start + duration,
                        all_day=all_day,
                        description=description,
                        recurrence=recurrence,
                        location=location,
                        url=url,
                        alert_minutes_before=_extract_alarm_minutes_before(master, start),
                        cancelled=False,
                    )
                )

        if not masters:
            for component in components:
                start = _get_dt(component, "dtstart")
                end = _get_dt(component, "dtend") or start
                if not start or not end:
                    continue
                if not _event_intersects_window(start, end, window_start, window_end):
                    continue
                rec_dt = _recurrence_id_from_component(component)
                rec_id = recurrence_id_str(rec_dt) if rec_dt else None
                events.append(
                    _build_event(
                        source_id=source_id,
                        uid=uid,
                        recurrence_id=rec_id,
                        title=str(component.get("summary", "Untitled")),
                        start=start,
                        end=end,
                        all_day=_is_all_day(component),
                        description=_event_text(component, "description"),
                        recurrence=normalize_rrule(component.get("rrule")),
                        location=_event_text(component, "location"),
                        url=_event_text(component, "url"),
                        alert_minutes_before=_extract_alarm_minutes_before(component, start),
                        cancelled=_event_cancelled(component),
                    )
                )
    return events


def _recurrence_id_str(dt: datetime) -> str:
    """Format a datetime as RECURRENCE-ID value for instance id (UTC, no spaces)."""
    return recurrence_id_str(dt)


def _parse_vtodo_component(
    component,
) -> tuple[str, datetime | None, bool, str, str | None, int | None, str | None, list[int] | None]:
    """Extract (uid, due, completed, summary, description, priority, recurrence, alert_minutes_before) from a VTODO."""
    uid = str(component.get("uid", ""))
    summary = str(component.get("summary", "Untitled"))
    completed = str(component.get("completed", "")).strip() != ""
    due = _get_dt(component, "due")
    desc = component.get("description")
    description = str(desc) if desc is not None else None
    priority = component.get("priority")
    priority = int(priority) if priority is not None else None
    recurrence = normalize_rrule(component.get("rrule"))
    due_or_start = due or _get_dt(component, "dtstart")
    alert_minutes_before = _extract_alarm_minutes_before(component, due_or_start)
    return uid, due, completed, summary, description, priority, recurrence, alert_minutes_before


def _recurrence_id_from_component(component) -> datetime | None:
    """Get RECURRENCE-ID from a VTODO component if present."""
    val = component.get("recurrence-id")
    if val is None:
        return None
    return _get_dt(component, "recurrence-id")


def _todo_due_in_window(
    due: datetime | None,
    window_start: datetime | None,
    window_end: datetime | None,
) -> bool:
    if window_start is None or window_end is None:
        return True
    if due is None:
        return True
    return window_start <= due <= window_end


def _parse_simple_rrule(recurrence: str) -> tuple[str, int, int | None, datetime | None] | None:
    parts: dict[str, str] = {}
    for segment in recurrence.split(";"):
        if "=" not in segment:
            continue
        key, value = segment.split("=", 1)
        parts[key.strip().upper()] = value.strip().upper()
    freq = parts.get("FREQ")
    if freq not in {"DAILY", "WEEKLY"}:
        return None
    unsupported = {
        "BYSECOND",
        "BYMINUTE",
        "BYHOUR",
        "BYDAY",
        "BYMONTHDAY",
        "BYYEARDAY",
        "BYWEEKNO",
        "BYMONTH",
        "BYSETPOS",
        "WKST",
    }
    if any(key in parts for key in unsupported):
        return None
    try:
        interval = int(parts.get("INTERVAL", "1"))
        if interval <= 0:
            return None
    except ValueError:
        return None
    count: int | None = None
    if "COUNT" in parts:
        try:
            count = int(parts["COUNT"])
        except ValueError:
            return None
    until: datetime | None = None
    until_raw = parts.get("UNTIL")
    if until_raw:
        until = recurrence_id_str_to_dt(until_raw)
        if until is None:
            return None
    return freq, interval, count, until


def _simple_occurrence_on_or_after(
    due_start: datetime,
    rule_spec: tuple[str, int, int | None, datetime | None],
    start: datetime,
) -> datetime | None:
    freq, interval, count, until = rule_spec
    unit_days = interval * (7 if freq == "WEEKLY" else 1)
    if start <= due_start:
        candidate = due_start
        index = 0
    else:
        elapsed_days = (start - due_start).total_seconds() / 86400
        steps = int(elapsed_days // unit_days)
        candidate = due_start + timedelta(days=steps * unit_days)
        if candidate < start:
            candidate += timedelta(days=unit_days)
            steps += 1
        index = steps
    if count is not None and index >= count:
        return None
    if until is not None:
        until_value = until if until.tzinfo else until.replace(tzinfo=timezone.utc)
        if candidate > until_value:
            return None
    return candidate


def _simple_occurrence_after(
    current: datetime,
    due_start: datetime | None,
    rule_spec: tuple[str, int, int | None, datetime | None],
) -> datetime | None:
    freq, interval, count, until = rule_spec
    unit_days = interval * (7 if freq == "WEEKLY" else 1)
    candidate = current + timedelta(days=unit_days)
    if count is not None and due_start is not None:
        index = int(round((candidate - due_start).total_seconds() / (unit_days * 86400)))
        if index >= count:
            return None
    if until is not None:
        until_value = until if until.tzinfo else until.replace(tzinfo=timezone.utc)
        if candidate > until_value:
            return None
    return candidate


def parse_todos_from_ical(
    ical_text: str | bytes,
    source_id: str,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> list[Todo]:
    """Parse VCALENDAR/VTODO from .ics content. Recurring VTODOs are expanded into
    one Todo per instance (only the next occurrence, like iPhone Reminders); completed instances use RECURRENCE-ID exceptions.
    """
    if isinstance(ical_text, str):
        ical_text = ical_text.encode("utf-8")
    window_start = _to_naive_utc(window_start)
    window_end = _to_naive_utc(window_end)
    cal = icalendar.Calendar.from_ical(ical_text)
    if not cal:
        return []
    components = [c for c in cal.walk() if c.name == "VTODO"]
    # Group by UID: master (has RRULE) + exceptions (have RECURRENCE-ID); exceptions include cancelled flag
    by_uid: dict[
        str,
        list[
            tuple[
                datetime | None,
                bool,
                datetime | None,
                str,
                str | None,
                int | None,
                str,
                bool,
                list[int] | None,
            ]
        ],
    ] = {}
    masters: dict[
        str, tuple[datetime | None, str, str | None, int | None, str, list[int] | None]
    ] = {}
    for component in components:
        uid, due, completed, summary, description, priority, recurrence, alert_minutes_before = (
            _parse_vtodo_component(component)
        )
        if not uid:
            continue
        rec_id = _recurrence_id_from_component(component)
        status = (component.get("status") or "").upper()
        cancelled = status == "CANCELLED"
        if recurrence:
            masters[uid] = (due, summary, description, priority, recurrence, alert_minutes_before)
        if rec_id is not None:
            if uid not in by_uid:
                by_uid[uid] = []
            by_uid[uid].append(
                (
                    rec_id,
                    completed,
                    due,
                    summary,
                    description,
                    priority,
                    recurrence or "",
                    cancelled,
                    alert_minutes_before,
                )
            )
    todos: list[Todo] = []
    seen_uid_no_rrule: set[str] = set()
    for component in components:
        uid, due, completed, summary, description, priority, recurrence, alert_minutes_before = (
            _parse_vtodo_component(component)
        )
        if not uid:
            continue
        rec_id = _recurrence_id_from_component(component)
        if recurrence:
            # Recurring master: expand to instances
            due_start = due or datetime.now(timezone.utc)
            if due_start.tzinfo is None:
                due_start = due_start.replace(tzinfo=timezone.utc)
            rule = parse_rrule(recurrence, due_start)
            if rule is None:
                # Fallback: single todo as before
                todos.append(
                    Todo(
                        id=f"{source_id}::{uid}",
                        source_id=source_id,
                        summary=summary,
                        completed=completed,
                        due=due,
                        description=description,
                        priority=priority,
                        recurrence=recurrence,
                        alert_minutes_before=alert_minutes_before,
                    )
                )
                continue
            # Show all completed instances and the next incomplete occurrence.
            # Completed instances are represented as one-off todos (no recurrence),
            # matching iOS Reminders behavior.
            now = datetime.now(timezone.utc)
            effective_window_start = (
                window_start if window_start is not None else _to_naive_utc(now - timedelta(days=1))
            )
            effective_window_end = window_end
            effective_window_start_rrule = (
                effective_window_start
                if effective_window_start is None or effective_window_start.tzinfo
                else effective_window_start.replace(tzinfo=timezone.utc)
            )
            effective_window_end_rrule = (
                effective_window_end
                if effective_window_end is None or effective_window_end.tzinfo
                else effective_window_end.replace(tzinfo=timezone.utc)
            )
            if due_start is not None and effective_window_start_rrule is not None:
                start = max(due_start, effective_window_start_rrule)
            else:
                start = due_start or effective_window_start_rrule
            if start is None:
                continue
            simple_rule_spec = _parse_simple_rrule(recurrence)
            exceptions_by_rec: dict[
                str,
                tuple[
                    datetime | None,
                    bool,
                    datetime | None,
                    str,
                    str | None,
                    int | None,
                    str,
                    bool,
                    list[int] | None,
                ],
            ] = {}
            for r in by_uid.get(uid, []):
                rec_dt = r[0]
                if rec_dt is None:
                    continue
                rec_str_k = _recurrence_id_str(rec_dt)
                rec_date_k = rec_dt.strftime("%Y%m%d")
                # Prefer CANCELLED over anything; then prefer COMPLETED over incomplete (same instance can have both after uncomplete then complete again).
                existing = exceptions_by_rec.get(rec_str_k)
                if existing is None or r[7] or r[1]:
                    exceptions_by_rec[rec_str_k] = r
                existing_d = exceptions_by_rec.get(rec_date_k)
                if existing_d is None or r[7] or r[1]:
                    exceptions_by_rec[rec_date_k] = r
            completed_list: list[
                tuple[str, str, datetime | None, str | None, int | None, list[int] | None]
            ] = []
            occ = (
                _simple_occurrence_on_or_after(due_start, simple_rule_spec, start)
                if simple_rule_spec is not None
                else next_occurrence_on_or_after(rule, start)
            )
            while occ is not None:
                if effective_window_end_rrule is not None and occ > effective_window_end_rrule:
                    break
                rec_str = _recurrence_id_str(occ)
                exc = exceptions_by_rec.get(rec_str) or exceptions_by_rec.get(
                    occ.strftime("%Y%m%d")
                )
                if exc is not None:
                    (
                        rec_dt_exc,
                        exc_completed,
                        exc_due,
                        exc_summary,
                        exc_desc,
                        exc_pri,
                        _,
                        exc_cancelled,
                        exc_alert,
                    ) = exc
                    if exc_cancelled:
                        occ = (
                            _simple_occurrence_after(occ, due_start, simple_rule_spec)
                            if simple_rule_spec is not None
                            else next_occurrence_strictly_after(rule, occ)
                        )
                        continue
                    if exc_completed:
                        rec_str_id = _recurrence_id_str(rec_dt_exc) if rec_dt_exc else rec_str
                        due_val = exc_due or occ
                        if due_val and getattr(due_val, "tzinfo", None):
                            due_val = _to_naive_utc(due_val)
                        if _todo_due_in_window(due_val, window_start, window_end):
                            completed_list.append(
                                (
                                    rec_str_id,
                                    exc_summary or summary,
                                    due_val,
                                    exc_desc if exc_desc is not None else description,
                                    exc_pri if exc_pri is not None else priority,
                                    exc_alert if exc_alert is not None else alert_minutes_before,
                                )
                            )
                        occ = (
                            _simple_occurrence_after(occ, due_start, simple_rule_spec)
                            if simple_rule_spec is not None
                            else next_occurrence_strictly_after(rule, occ)
                        )
                        continue
                    # Incomplete exception: next instance to show
                    rec_str_id = _recurrence_id_str(rec_dt_exc) if rec_dt_exc else rec_str
                    due_val = exc_due or occ
                    if due_val and getattr(due_val, "tzinfo", None):
                        due_val = _to_naive_utc(due_val)
                    for lc_id, lc_sum, lc_due, lc_desc, lc_pri, lc_alert in completed_list:
                        todos.append(
                            Todo(
                                id=f"{source_id}::{uid}::{lc_id}",
                                source_id=source_id,
                                summary=lc_sum,
                                completed=True,
                                due=lc_due,
                                description=lc_desc,
                                priority=lc_pri,
                                recurrence=None,
                                alert_minutes_before=lc_alert,
                            )
                        )
                    if _todo_due_in_window(due_val, window_start, window_end):
                        todos.append(
                            Todo(
                                id=f"{source_id}::{uid}::{rec_str_id}",
                                source_id=source_id,
                                summary=exc_summary or summary,
                                completed=False,
                                due=due_val,
                                description=exc_desc if exc_desc is not None else description,
                                priority=exc_pri if exc_pri is not None else priority,
                                recurrence=recurrence,
                                alert_minutes_before=exc_alert
                                if exc_alert is not None
                                else alert_minutes_before,
                            )
                        )
                    break
                # No exception: next instance from rule
                due_val = _to_naive_utc(occ) if (occ and getattr(occ, "tzinfo", None)) else occ
                for lc_id, lc_sum, lc_due, lc_desc, lc_pri, lc_alert in completed_list:
                    todos.append(
                        Todo(
                            id=f"{source_id}::{uid}::{lc_id}",
                            source_id=source_id,
                            summary=lc_sum,
                            completed=True,
                            due=lc_due,
                            description=lc_desc,
                            priority=lc_pri,
                            recurrence=None,
                            alert_minutes_before=lc_alert,
                        )
                    )
                if _todo_due_in_window(due_val, window_start, window_end):
                    todos.append(
                        Todo(
                            id=f"{source_id}::{uid}::{rec_str}",
                            source_id=source_id,
                            summary=summary,
                            completed=False,
                            due=due_val,
                            description=description,
                            priority=priority,
                            recurrence=recurrence,
                            alert_minutes_before=alert_minutes_before,
                        )
                    )
                break
            continue
        if rec_id is not None:
            continue  # already handled as exception above
        if uid in seen_uid_no_rrule:
            continue
        seen_uid_no_rrule.add(uid)
        # Non-recurring VTODO
        if _todo_due_in_window(due, window_start, window_end):
            todos.append(
                Todo(
                    id=f"{source_id}::{uid}",
                    source_id=source_id,
                    summary=summary,
                    completed=completed,
                    due=due,
                    description=description,
                    priority=priority,
                    recurrence=None,
                    alert_minutes_before=alert_minutes_before,
                )
            )
    return todos


def event_to_ical(event: Event) -> bytes:
    """Serialize a single Event to VCALENDAR with one VEVENT."""
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Calslop//EN")
    cal.add("version", "2.0")
    vevent = icalendar.Event()
    # UID is required; use part after :: or generate one for new events
    uid = event.id.split("::")[-1] if (event.id and "::" in event.id) else (event.id or "")
    if not uid or not uid.strip():
        uid = f"calslop-{uuid.uuid4().hex}@calslop"
    vevent.add("uid", uid)
    # DTSTAMP is required by RFC 5545 and many CalDAV servers
    vevent.add("dtstamp", datetime.now(timezone.utc))
    vevent.add("summary", event.title)
    if event.all_day:
        start_date = event.start.date()
        end_date = event.end.date() if event.end else start_date
        # DATE DTEND is exclusive for all-day events.
        end_exclusive = end_date if end_date > start_date else (start_date + timedelta(days=1))
        vevent.add("dtstart", start_date)
        vevent.add("dtend", end_exclusive)
    else:
        start_utc = _to_aware_utc(event.start)
        end_utc = _to_aware_utc(event.end)
        if start_utc is not None:
            vevent.add("dtstart", start_utc)
        if end_utc is not None:
            vevent.add("dtend", end_utc)
    if event.description:
        vevent.add("description", event.description)
    if event.location:
        vevent.add("location", event.location)
    recurrence = getattr(event, "recurrence", None)
    if recurrence:
        try:
            vevent.add("rrule", vRecur.from_ical(recurrence))
        except Exception:
            pass  # skip invalid RRULE
    if event.url:
        vevent.add("url", event.url)
    _set_display_alarm(vevent, getattr(event, "alert_minutes_before", None))
    cal.add_component(vevent)
    return cal.to_ical()


def todo_to_ical(todo: Todo) -> bytes:
    """Serialize a single Todo to VCALENDAR with one VTODO."""
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Calslop//EN")
    cal.add("version", "2.0")
    vtodo = icalendar.Todo()
    uid = todo.id.split("::")[-1] if (todo.id and "::" in todo.id) else (todo.id or "")
    if not uid or not uid.strip():
        uid = f"calslop-todo-{uuid.uuid4().hex}@calslop"
    vtodo.add("uid", uid)
    vtodo.add("dtstamp", datetime.now(timezone.utc))
    vtodo.add("summary", todo.summary)
    if todo.completed:
        vtodo.add("completed", datetime.now(timezone.utc))
    if todo.due:
        due_local = _to_aware_local(todo.due)
        if due_local is not None:
            vtodo.add("dtstart", due_local)
            vtodo.add("due", due_local)
    if todo.description:
        vtodo.add("description", todo.description)
    if todo.priority is not None:
        vtodo.add("priority", todo.priority)
    recurrence = getattr(todo, "recurrence", None)
    if recurrence:
        try:
            vtodo.add("rrule", vRecur.from_ical(recurrence))
        except Exception:
            pass
    _set_display_alarm(vtodo, getattr(todo, "alert_minutes_before", None))
    cal.add_component(vtodo)
    return cal.to_ical()


def is_recurrence_id_str(s: str) -> bool:
    """True if s looks like a RECURRENCE-ID value (YYYYMMDD or YYYYMMDDTHHMMSSZ)."""
    if not s or len(s) < 8:
        return False
    if len(s) == 8 and s.isdigit():
        return True
    if len(s) >= 15 and s[8:9] == "T" and (s.endswith("Z") or s[-1].isdigit()):
        return s[:8].isdigit() and s[9:15].isdigit()
    return False


def todo_id_to_master_id(todo_id: str) -> str | None:
    """If todo_id is a recurring instance (has recurrence-id suffix), return master id (source_id::uid). Else return None."""
    parts = todo_id.split("::")
    if len(parts) >= 2 and is_recurrence_id_str(parts[-1]):
        return "::".join(parts[:-1])
    return None


def recurrence_id_str_to_dt(recurrence_id_str: str) -> datetime | None:
    """Parse recurrence_id_str (e.g. 20250305T090000Z) to datetime."""
    try:
        return datetime.strptime(recurrence_id_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(recurrence_id_str, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def merge_instance_todo_into_ical(ical_bytes: bytes, todo: Todo, recurrence_id_str: str) -> bytes:
    """Merge an instance todo (recurring occurrence) into an existing VCALENDAR. Adds or updates the VTODO with RECURRENCE-ID=recurrence_id_str. Returns new ical bytes."""
    cal = icalendar.Calendar.from_ical(ical_bytes)
    if not cal:
        return ical_bytes
    parts = todo.id.split("::")
    uid = (
        parts[-2]
        if len(parts) >= 2 and is_recurrence_id_str(parts[-1])
        else (parts[-1] if parts else "")
    )
    rec_dt = recurrence_id_str_to_dt(recurrence_id_str)
    if not rec_dt:
        return ical_bytes
    # Normalize recurrence_id for matching (both DATE and DATE-TIME)
    rec_str_dt = _recurrence_id_str(rec_dt)
    rec_str_date = rec_dt.strftime("%Y%m%d")
    found = None
    for component in list(cal.subcomponents):
        if getattr(component, "name", None) != "VTODO":
            continue
        if str(component.get("uid", "")) != uid:
            continue
        comp_rec = _recurrence_id_from_component(component)
        if comp_rec is None:
            continue
        comp_str = _recurrence_id_str(comp_rec)
        comp_date = comp_rec.strftime("%Y%m%d")
        if (
            comp_str == rec_str_dt
            or comp_str == recurrence_id_str
            or comp_date == rec_str_date
            or comp_date == rec_str_dt[:8]
        ):
            found = component
            break
    if found is not None:
        cal.subcomponents.remove(found)
    # Add or replace with the instance data
    vtodo = icalendar.Todo()
    vtodo.add("uid", uid)
    vtodo.add("dtstamp", datetime.now(timezone.utc))
    vtodo.add("summary", todo.summary)
    rec_local = _to_aware_local(rec_dt)
    if rec_local is not None:
        vtodo.add("recurrence-id", rec_local)
    if todo.completed:
        vtodo.add("completed", datetime.now(timezone.utc))
    if todo.due:
        due_local = _to_aware_local(todo.due)
        if due_local is not None:
            vtodo.add("dtstart", due_local)
            vtodo.add("due", due_local)
    if todo.description:
        vtodo.add("description", todo.description)
    if todo.priority is not None:
        vtodo.add("priority", todo.priority)
    _set_display_alarm(vtodo, getattr(todo, "alert_minutes_before", None))
    cal.add_component(vtodo)
    _update_master_vtodo_metadata(cal, uid, todo.summary, todo.description, todo.priority)
    return cal.to_ical()


def _update_master_vtodo_metadata(
    cal, uid: str, summary: str, description: str | None, priority: int | None
) -> None:
    """Update the master VTODO (same UID, no RECURRENCE-ID) so series summary/description/priority stay in sync."""
    for component in list(cal.subcomponents):
        if getattr(component, "name", None) != "VTODO":
            continue
        if str(component.get("uid", "")) != uid:
            continue
        if _recurrence_id_from_component(component) is not None:
            continue
        if "summary" in component:
            del component["summary"]
        component.add("summary", summary)
        if description is not None:
            if "description" in component:
                del component["description"]
            component.add("description", description)
        elif "description" in component:
            del component["description"]
        if priority is not None:
            if "priority" in component:
                del component["priority"]
            component.add("priority", priority)
        elif "priority" in component:
            del component["priority"]
        break


def build_exception_vtodo(
    uid: str,
    recurrence_id_str: str,
    summary: str,
    due: datetime | None,
    description: str | None,
    priority: int | None,
    alert_minutes_before: list[int] | None = None,
) -> bytes:
    """Build a VTODO component for a completed RECURRENCE-ID exception (same UID as master)."""
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Calslop//EN")
    cal.add("version", "2.0")
    vtodo = icalendar.Todo()
    vtodo.add("uid", uid)
    vtodo.add("dtstamp", datetime.now(timezone.utc))
    vtodo.add("summary", summary)
    rec_dt = recurrence_id_str_to_dt(recurrence_id_str)
    if rec_dt:
        rec_local = _to_aware_local(rec_dt)
        if rec_local is not None:
            vtodo.add("recurrence-id", rec_local)
    vtodo.add("completed", datetime.now(timezone.utc))
    if due:
        due_local = _to_aware_local(due)
        if due_local is not None:
            vtodo.add("dtstart", due_local)
            vtodo.add("due", due_local)
    if description:
        vtodo.add("description", description)
    if priority is not None:
        vtodo.add("priority", priority)
    _set_display_alarm(vtodo, alert_minutes_before)
    cal.add_component(vtodo)
    return cal.to_ical()


def build_cancelled_exception_vtodo(uid: str, recurrence_id_str: str) -> bytes:
    """Build a VTODO component for a cancelled RECURRENCE-ID instance (same UID as master). Deleted instance, not completed."""
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Calslop//EN")
    cal.add("version", "2.0")
    vtodo = icalendar.Todo()
    vtodo.add("uid", uid)
    vtodo.add("dtstamp", datetime.now(timezone.utc))
    vtodo.add("summary", "")
    rec_dt = recurrence_id_str_to_dt(recurrence_id_str)
    if rec_dt:
        rec_local = _to_aware_local(rec_dt)
        if rec_local is not None:
            vtodo.add("recurrence-id", rec_local)
    vtodo.add("status", "CANCELLED")
    cal.add_component(vtodo)
    return cal.to_ical()


def next_recurrence_occurrence(recurrence: str, after_dt: datetime | None) -> datetime | None:
    """Return the first recurrence occurrence strictly after after_dt, or None if no next.
    Uses the todo's due (or now) as dtstart for the RRULE.
    """
    if not recurrence:
        return None
    recurrence = recurrence.strip().replace("\r\n", "\n").replace("\r", "\n")
    if not recurrence:
        return None
    try:
        dtstart = after_dt or datetime.now(timezone.utc)
        if dtstart.tzinfo is None:
            dtstart = dtstart.replace(tzinfo=timezone.utc)
        rule = rrulestr(recurrence, dtstart=dtstart)
        next_dt = rule.after(dtstart)
        if next_dt is None:
            return None
        if next_dt.tzinfo is None:
            next_dt = next_dt.replace(tzinfo=timezone.utc)
        return next_dt
    except Exception:
        return None
