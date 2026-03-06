"""Parse icalendar components into Event/Todo DTOs."""
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import icalendar
from icalendar import vRecur
from dateutil.rrule import rrulestr

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


def _recurrence_id_str(dt: datetime) -> str:
    """Format a datetime as RECURRENCE-ID value for instance id (UTC, no spaces)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _parse_vtodo_component(component) -> tuple[str, datetime | None, bool, str, str | None, int | None, str | None]:
    """Extract (uid, due, completed, summary, description, priority, recurrence) from a VTODO."""
    uid = str(component.get("uid", ""))
    summary = str(component.get("summary", "Untitled"))
    completed = str(component.get("completed", "")).strip() != ""
    due = _get_dt(component, "due")
    desc = component.get("description")
    description = str(desc) if desc is not None else None
    priority = component.get("priority")
    priority = int(priority) if priority is not None else None
    rrule = component.get("rrule")
    recurrence = rrule.to_ical().decode() if rrule and hasattr(rrule, "to_ical") else None
    return uid, due, completed, summary, description, priority, recurrence


def _recurrence_id_from_component(component) -> datetime | None:
    """Get RECURRENCE-ID from a VTODO component if present."""
    val = component.get("recurrence-id")
    if val is None:
        return None
    return _get_dt(component, "recurrence-id")


def parse_todos_from_ical(ical_text: str | bytes, source_id: str) -> list[Todo]:
    """Parse VCALENDAR/VTODO from .ics content. Recurring VTODOs are expanded into
    one Todo per instance (only the next occurrence, like iPhone Reminders); completed instances use RECURRENCE-ID exceptions.
    """
    if isinstance(ical_text, str):
        ical_text = ical_text.encode("utf-8")
    cal = icalendar.Calendar.from_ical(ical_text)
    if not cal:
        return []
    components = [c for c in cal.walk() if c.name == "VTODO"]
    # Group by UID: master (has RRULE) + exceptions (have RECURRENCE-ID)
    by_uid: dict[str, list[tuple[datetime | None, bool, datetime | None, str, str | None, int | None, str | None]]] = {}
    masters: dict[str, tuple[datetime | None, str, str | None, int | None, str]] = {}
    for component in components:
        uid, due, completed, summary, description, priority, recurrence = _parse_vtodo_component(component)
        if not uid:
            continue
        rec_id = _recurrence_id_from_component(component)
        if recurrence:
            masters[uid] = (due, summary, description, priority, recurrence)
        if rec_id is not None:
            if uid not in by_uid:
                by_uid[uid] = []
            by_uid[uid].append((rec_id, completed, due, summary, description, priority, recurrence or ""))
    todos: list[Todo] = []
    seen_uid_no_rrule: set[str] = set()
    for component in components:
        uid, due, completed, summary, description, priority, recurrence = _parse_vtodo_component(component)
        if not uid:
            continue
        rec_id = _recurrence_id_from_component(component)
        if recurrence:
            # Recurring master: expand to instances
            due_start = due or datetime.now(timezone.utc)
            if due_start.tzinfo is None:
                due_start = due_start.replace(tzinfo=timezone.utc)
            recurrence_clean = recurrence.strip().replace("\r\n", "\n").replace("\r", "\n")
            try:
                rule = rrulestr(recurrence_clean, dtstart=due_start)
            except Exception:
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
                    )
                )
                continue
            # Only the next (incomplete) occurrence, like iPhone Reminders
            now = datetime.now(timezone.utc)
            start = max(due_start, now - timedelta(days=1)) if due_start else now
            exceptions_by_rec: dict[str, tuple] = {}
            for r in by_uid.get(uid, []):
                rec_dt = r[0]
                if rec_dt is not None:
                    exceptions_by_rec[_recurrence_id_str(rec_dt)] = r
                    exceptions_by_rec[rec_dt.strftime("%Y%m%d")] = r
            for occ in rule:
                if occ < start:
                    continue
                rec_str = _recurrence_id_str(occ)
                exc = exceptions_by_rec.get(rec_str) or exceptions_by_rec.get(occ.strftime("%Y%m%d"))
                if exc is not None:
                    _, exc_completed, exc_due, exc_summary, exc_desc, exc_pri, _ = exc
                    if exc_completed:
                        continue  # skip completed instances, show the next one
                    instance_todo = Todo(
                        id=f"{source_id}::{uid}::{rec_str}",
                        source_id=source_id,
                        summary=exc_summary or summary,
                        completed=False,
                        due=exc_due or occ,
                        description=exc_desc if exc_desc is not None else description,
                        priority=exc_pri if exc_pri is not None else priority,
                        recurrence=recurrence,
                    )
                else:
                    instance_todo = Todo(
                        id=f"{source_id}::{uid}::{rec_str}",
                        source_id=source_id,
                        summary=summary,
                        completed=False,
                        due=occ,
                        description=description,
                        priority=priority,
                        recurrence=recurrence,
                    )
                todos.append(instance_todo)
                break  # only the next occurrence
            continue
        if rec_id is not None:
            continue  # already handled as exception above
        if uid in seen_uid_no_rrule:
            continue
        seen_uid_no_rrule.add(uid)
        # Non-recurring VTODO
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


def recurrence_id_str_to_dt(recurrence_id_str: str) -> datetime | None:
    """Parse recurrence_id_str (e.g. 20250305T090000Z) to datetime."""
    try:
        return datetime.strptime(recurrence_id_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(recurrence_id_str, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def build_exception_vtodo(
    uid: str,
    recurrence_id_str: str,
    summary: str,
    due: datetime | None,
    description: str | None,
    priority: int | None,
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
        vtodo.add("recurrence-id", rec_dt)
    vtodo.add("completed", datetime.now(timezone.utc))
    if due:
        vtodo.add("due", due)
    if description:
        vtodo.add("description", description)
    if priority is not None:
        vtodo.add("priority", priority)
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
