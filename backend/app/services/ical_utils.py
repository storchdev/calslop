"""Parse icalendar components into Event/Todo DTOs."""
import uuid
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import icalendar
from icalendar import vRecur

from app.models.dtos import Event, Todo


def _to_naive_utc(dt: datetime | date | None) -> datetime | None:
    if dt is None:
        return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return datetime.combine(dt, datetime.min.time())
    if getattr(dt, "tzinfo", None):
        return dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return dt


def _get_dt(component: icalendar.cal.Component, key: str) -> datetime | None:
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


def _is_all_day(component: icalendar.cal.Component) -> bool:
    dtstart = component.get("dtstart")
    if dtstart is None:
        return False
    dt = getattr(dtstart, "dt", None)
    return isinstance(dt, date) and not isinstance(dt, datetime)


def parse_events_from_ical(ical_text: str | bytes, source_id: str) -> list[Event]:
    """Parse VCALENDAR/VEVENT from .ics content. Returns list of Event DTOs."""
    if isinstance(ical_text, str):
        ical_text = ical_text.encode("utf-8")
    cal = icalendar.Calendar.from_ical(ical_text)
    if not cal:
        return []
    events: list[Event] = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        uid = str(component.get("uid", ""))
        if not uid:
            continue
        start = _get_dt(component, "dtstart")
        end = _get_dt(component, "dtend")
        if not start:
            continue
        if not end:
            end = start
        summary = str(component.get("summary", "Untitled"))
        desc = component.get("description")
        description = str(desc) if desc is not None else None
        location = component.get("location")
        location = str(location) if location is not None else None
        url_val = component.get("url")
        url = str(url_val) if url_val is not None else None
        status = (component.get("status") or "").upper()
        cancelled = status == "CANCELLED"
        events.append(
            Event(
                id=f"{source_id}::{uid}",
                source_id=source_id,
                title=summary,
                start=start,
                end=end,
                all_day=_is_all_day(component),
                description=description,
                recurrence=None,  # Could parse RRULE if needed
                location=location,
                url=url,
                cancelled=cancelled,
            )
        )
    return events


def parse_todos_from_ical(ical_text: str | bytes, source_id: str) -> list[Todo]:
    """Parse VCALENDAR/VTODO from .ics content."""
    if isinstance(ical_text, str):
        ical_text = ical_text.encode("utf-8")
    cal = icalendar.Calendar.from_ical(ical_text)
    if not cal:
        return []
    todos: list[Todo] = []
    for component in cal.walk():
        if component.name != "VTODO":
            continue
        uid = str(component.get("uid", ""))
        if not uid:
            continue
        summary = str(component.get("summary", "Untitled"))
        completed = str(component.get("completed", "")).strip() != ""
        due = _get_dt(component, "due")
        desc = component.get("description")
        description = str(desc) if desc is not None else None
        priority = component.get("priority")
        priority = int(priority) if priority is not None else None
        rrule = component.get("rrule")
        recurrence = rrule.to_ical().decode() if rrule and hasattr(rrule, "to_ical") else None
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
    vevent.add("dtstart", event.start)
    vevent.add("dtend", event.end)
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
        vtodo.add("due", todo.due)
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
    cal.add_component(vtodo)
    return cal.to_ical()
