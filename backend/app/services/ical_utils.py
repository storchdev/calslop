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
    # Group by UID: master (has RRULE) + exceptions (have RECURRENCE-ID); exceptions include cancelled flag
    _exc = tuple[datetime | None, bool, datetime | None, str, str | None, int | None, str, bool]
    by_uid: dict[str, list[_exc]] = {}
    masters: dict[str, tuple[datetime | None, str, str | None, int | None, str]] = {}
    for component in components:
        uid, due, completed, summary, description, priority, recurrence = _parse_vtodo_component(component)
        if not uid:
            continue
        rec_id = _recurrence_id_from_component(component)
        status = (component.get("status") or "").upper()
        cancelled = status == "CANCELLED"
        if recurrence:
            masters[uid] = (due, summary, description, priority, recurrence)
        if rec_id is not None:
            if uid not in by_uid:
                by_uid[uid] = []
            by_uid[uid].append((rec_id, completed, due, summary, description, priority, recurrence or "", cancelled))
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
            # Show all completed instances and the next incomplete occurrence.
            now = datetime.now(timezone.utc)
            start = max(due_start, now - timedelta(days=1)) if due_start else now
            exceptions_by_rec: dict[str, _exc] = {}
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
            completed_list: list[tuple[str, str, datetime | None, str | None, int | None]] = []
            for occ in rule:
                if occ < start:
                    continue
                rec_str = _recurrence_id_str(occ)
                exc = exceptions_by_rec.get(rec_str) or exceptions_by_rec.get(occ.strftime("%Y%m%d"))
                if exc is not None:
                    rec_dt_exc, exc_completed, exc_due, exc_summary, exc_desc, exc_pri, _, exc_cancelled = exc
                    if exc_cancelled:
                        continue
                    if exc_completed:
                        rec_str_id = _recurrence_id_str(rec_dt_exc) if rec_dt_exc else rec_str
                        due_val = exc_due or occ
                        if due_val and getattr(due_val, "tzinfo", None):
                            due_val = _to_naive_utc(due_val)
                        completed_list.append(
                            (
                                rec_str_id,
                                exc_summary or summary,
                                due_val,
                                exc_desc if exc_desc is not None else description,
                                exc_pri if exc_pri is not None else priority,
                            )
                        )
                        continue
                    # Incomplete exception: next instance to show
                    rec_str_id = _recurrence_id_str(rec_dt_exc) if rec_dt_exc else rec_str
                    due_val = exc_due or occ
                    if due_val and getattr(due_val, "tzinfo", None):
                        due_val = _to_naive_utc(due_val)
                    for lc_id, lc_sum, lc_due, lc_desc, lc_pri in completed_list:
                        todos.append(
                            Todo(
                                id=f"{source_id}::{uid}::{lc_id}",
                                source_id=source_id,
                                summary=lc_sum,
                                completed=True,
                                due=lc_due,
                                description=lc_desc,
                                priority=lc_pri,
                                recurrence=recurrence,
                            )
                        )
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
                        )
                    )
                    break
                # No exception: next instance from rule
                due_val = _to_naive_utc(occ) if (occ and getattr(occ, "tzinfo", None)) else occ
                for lc_id, lc_sum, lc_due, lc_desc, lc_pri in completed_list:
                    todos.append(
                        Todo(
                            id=f"{source_id}::{uid}::{lc_id}",
                            source_id=source_id,
                            summary=lc_sum,
                            completed=True,
                            due=lc_due,
                            description=lc_desc,
                            priority=lc_pri,
                            recurrence=recurrence,
                        )
                    )
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
    uid = parts[-2] if len(parts) >= 2 and is_recurrence_id_str(parts[-1]) else (parts[-1] if parts else "")
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
        if comp_str == rec_str_dt or comp_str == recurrence_id_str or comp_date == rec_str_date or comp_date == rec_str_dt[:8]:
            found = component
            break
    if found is not None:
        cal.subcomponents.remove(found)
    # Add or replace with the instance data
    vtodo = icalendar.Todo()
    vtodo.add("uid", uid)
    vtodo.add("dtstamp", datetime.now(timezone.utc))
    vtodo.add("summary", todo.summary)
    vtodo.add("recurrence-id", rec_dt)
    if todo.completed:
        vtodo.add("completed", datetime.now(timezone.utc))
    if todo.due:
        vtodo.add("due", todo.due)
    if todo.description:
        vtodo.add("description", todo.description)
    if todo.priority is not None:
        vtodo.add("priority", todo.priority)
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
        vtodo.add("recurrence-id", rec_dt)
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
