from datetime import datetime

import caldav
import icalendar
from caldav.elements import dav

from app.models.dtos import Event, Source, Todo
from app.services.ical_utils import (
    parse_events_from_ical,
    parse_todos_from_ical,
    build_exception_vtodo,
    build_cancelled_exception_vtodo,
    is_recurrence_id_str,
    merge_instance_todo_into_ical,
    todo_id_to_master_id,
    _update_master_vtodo_metadata,
)
from app.services.sources.base import FetchResult, SourceDriver


class CalDAVDriver(SourceDriver):
    """CalDAV server subscription; supports events and todos, read/write."""

    def _get_client(self, source: Source) -> caldav.DAVClient | None:
        url = source.config.get("url")
        username = source.config.get("username", "")
        password = source.config.get("password", "")
        if not url:
            return None
        try:
            return caldav.DAVClient(url=url, username=username, password=password)
        except Exception:
            return None

    def fetch(
        self,
        source: Source,
        start: str | None = None,
        end: str | None = None,
    ) -> FetchResult:
        client = self._get_client(source)
        if not client:
            return FetchResult([], [], errors=["Invalid CalDAV config or connection failed"])
        principal = client.principal()
        if not principal:
            return FetchResult([], [], errors=["No principal"])
        all_events: list[Event] = []
        all_todos: list[Todo] = []
        errors: list[str] = []
        try:
            calendars = principal.calendars()
            for cal in calendars:
                try:
                    if start and end:
                        events_fetched = cal.date_search(
                            start=datetime.fromisoformat(start.replace("Z", "+00:00")),
                            end=datetime.fromisoformat(end.replace("Z", "+00:00")),
                        )
                    else:
                        events_fetched = cal.events()
                    for ev in events_fetched:
                        if hasattr(ev, "data") and ev.data:
                            ics_data = ev.data
                        else:
                            ics_data = ev.icalendar_component.to_ical() if hasattr(ev, "icalendar_component") else b""
                        if isinstance(ics_data, bytes):
                            ics_data = ics_data.decode("utf-8", errors="replace")
                        cal_id = f"{source.id}::{cal.id}" if getattr(cal, "id", None) else source.id
                        all_events.extend(parse_events_from_ical(ics_data, cal_id))
                except Exception as e:
                    errors.append(f"Calendar {getattr(cal, 'id', cal)}: {e}")
            # Todo lists (CalDAV supports VTODO in calendar or separate todo list)
            try:
                todo_lists = getattr(principal, "todo_sets", lambda: [])()
                if not todo_lists and hasattr(principal, "calendars"):
                    # Some servers put todos in calendars. Request include_completed=True so completed tasks are returned.
                    for cal in principal.calendars():
                        try:
                            todos_method = getattr(cal, "todos", None) or getattr(cal, "get_todos", None)
                            if callable(todos_method):
                                todos_fetched = todos_method(include_completed=True)
                            else:
                                todos_fetched = []
                            for t in todos_fetched:
                                if hasattr(t, "data") and t.data:
                                    ics_data = t.data
                                else:
                                    ics_data = getattr(t, "icalendar_component", None)
                                    if ics_data:
                                        ics_data = ics_data.to_ical()
                                    else:
                                        ics_data = b""
                                if isinstance(ics_data, bytes):
                                    ics_data = ics_data.decode("utf-8", errors="replace")
                                cal_id = f"{source.id}::{getattr(cal, 'id', '')}"
                                all_todos.extend(parse_todos_from_ical(ics_data, cal_id))
                        except Exception as e:
                            errors.append(f"Todos {getattr(cal, 'id', cal)}: {e}")
                else:
                    for ts in todo_lists:
                        try:
                            todos_fetched = ts.todos(include_completed=True) if hasattr(ts, "todos") else []
                            for t in todos_fetched:
                                if hasattr(t, "data") and t.data:
                                    ics_data = t.data
                                else:
                                    ics_data = getattr(t, "icalendar_component", None)
                                    if ics_data:
                                        ics_data = ics_data.to_ical()
                                    else:
                                        ics_data = b""
                                if isinstance(ics_data, bytes):
                                    ics_data = ics_data.decode("utf-8", errors="replace")
                                all_todos.extend(parse_todos_from_ical(ics_data, source.id))
                        except Exception as e:
                            errors.append(str(e))
            except Exception as e:
                errors.append(f"Todos: {e}")
        except Exception as e:
            return FetchResult([], [], errors=[str(e)])
        return FetchResult(events=all_events, todos=all_todos, errors=errors or None)

    def can_write(self) -> bool:
        return True

    def create_event(self, source: Source, event: Event) -> Event | None:
        client = self._get_client(source)
        if not client:
            raise ValueError("CalDAV connection failed (check URL and credentials)")
        try:
            principal = client.principal()
            calendars = principal.calendars()
            if not calendars:
                raise ValueError("No calendars found on CalDAV account")
            cal = calendars[0]
            from app.services.ical_utils import event_to_ical
            ical_str = event_to_ical(event).decode("utf-8")
            new_ev = cal.save_event(ical_str)
            if new_ev and hasattr(new_ev, "id"):
                event = Event(**{**event.model_dump(), "id": f"{source.id}::{getattr(new_ev, 'id', event.id)}"})
            return event
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"CalDAV save failed: {e}") from e

    def update_event(self, source: Source, event: Event) -> Event | None:
        # CalDAV update: fetch event by id, save back with new data
        client = self._get_client(source)
        if not client:
            raise ValueError("CalDAV connection failed (check URL and credentials)")
        try:
            principal = client.principal()
            for cal in principal.calendars():
                events = cal.events()
                for ev in events:
                    ev_id = str(getattr(ev, "id", ""))
                    uid = event.id.split("::")[-1] if "::" in event.id else event.id
                    if ev_id and (event.id.endswith(ev_id) or uid in ev_id or ev_id.endswith(uid)):
                        from app.services.ical_utils import event_to_ical
                        ev.icalendar_instance = icalendar.Calendar.from_ical(event_to_ical(event))
                        ev.save()
                        return event
            raise ValueError("Event not found on CalDAV server")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"CalDAV update failed: {e}") from e

    def delete_event(self, source: Source, event_id: str) -> bool:
        try:
            principal = self._get_client(source).principal()
            for cal in principal.calendars():
                for ev in cal.events():
                    if event_id in str(getattr(ev, "id", "")) or (hasattr(ev, "id") and ev.id and event_id.endswith(ev.id)):
                        ev.delete()
                        return True
        except Exception:
            pass
        return False

    def create_todo(self, source: Source, todo: Todo) -> Todo | None:
        from app.services.ical_utils import todo_to_ical
        client = self._get_client(source)
        if not client:
            return None
        try:
            principal = client.principal()
            ical_str = todo_to_ical(todo).decode("utf-8")
            todo_sets = getattr(principal, "todo_sets", lambda: [])()
            if todo_sets:
                ts = todo_sets[0]
                ts.save_todo(ical_str)
                return todo
            # Many servers store todos in calendars, not todo_sets. Try each calendar.
            for cal in principal.calendars():
                save_todo = getattr(cal, "save_todo", None)
                if callable(save_todo):
                    try:
                        save_todo(ical_str)
                        return todo
                    except Exception:
                        continue
        except Exception:
            pass
        return None

    def _resource_uid_from_todo_id(self, todo_id: str) -> str:
        """Extract the UID that identifies the CalDAV resource (master VTODO). For instance ids, strip recurrence-id suffix."""
        parts = todo_id.split("::")
        if not parts:
            return ""
        if len(parts) >= 2 and is_recurrence_id_str(parts[-1]):
            return parts[-2]
        return parts[-1]

    def _todo_ids_match(self, our_id: str, caldav_todo) -> bool:
        """Match our todo id (source_id::uid or source_id::cal_id::uid, or instance with ::recurrence_id) against CalDAV object."""
        uid = self._resource_uid_from_todo_id(our_id)
        if not uid:
            return False
        t_id = str(getattr(caldav_todo, "id", "") or "")
        t_url = str(getattr(caldav_todo, "url", "") or "")
        if our_id in t_id or our_id in t_url or uid in t_id or uid in t_url:
            return True
        try:
            comp = getattr(caldav_todo, "icalendar_component", None)
            if comp:
                for c in (comp.walk() if hasattr(comp, "walk") else [comp]):
                    if getattr(c, "name", None) == "VTODO" and str(c.get("uid", "")) == uid:
                        return True
        except Exception:
            pass
        return False

    def add_recurrence_exception(
        self,
        source: Source,
        master_todo_id: str,
        recurrence_id_str: str,
        summary: str,
        due,
        description: str | None,
        priority: int | None,
        alert_minutes_before: list[int] | None,
    ) -> bool:
        """Add a completed RECURRENCE-ID exception to the calendar object that contains the master."""
        uid = self._resource_uid_from_todo_id(master_todo_id)
        if not uid:
            return False
        client = self._get_client(source)
        if not client:
            return False
        try:
            principal = client.principal()
            exc_bytes = build_exception_vtodo(
                uid, recurrence_id_str, summary, due, description, priority, alert_minutes_before
            )
            exc_cal = icalendar.Calendar.from_ical(exc_bytes)
            exc_vtodo = None
            for comp in exc_cal.walk():
                if comp.name == "VTODO":
                    exc_vtodo = comp
                    break
            if exc_vtodo is None:
                return False
            for cal in principal.calendars():
                todos_fn = getattr(cal, "todos", None) or getattr(cal, "get_todos", None)
                for t in (todos_fn(include_completed=True) if callable(todos_fn) else []):
                    if self._todo_ids_match(master_todo_id, t):
                        cal_inst = getattr(t, "icalendar_instance", None) or icalendar.Calendar.from_ical(
                            t.data if getattr(t, "data", None) else t.icalendar_component.to_ical()
                        )
                        if cal_inst:
                            cal_inst.add_component(exc_vtodo)
                            _update_master_vtodo_metadata(cal_inst, uid, summary, description, priority)
                            t.icalendar_instance = cal_inst
                            t.save()
                        return True
            for ts in getattr(principal, "todo_sets", lambda: [])():
                for t in (ts.todos(include_completed=True) if hasattr(ts, "todos") else []):
                    if self._todo_ids_match(master_todo_id, t):
                        cal_inst = getattr(t, "icalendar_instance", None) or icalendar.Calendar.from_ical(
                            t.data if getattr(t, "data", None) else t.icalendar_component.to_ical()
                        )
                        if cal_inst:
                            cal_inst.add_component(exc_vtodo)
                            _update_master_vtodo_metadata(cal_inst, uid, summary, description, priority)
                            t.icalendar_instance = cal_inst
                            t.save()
                        return True
        except Exception:
            pass
        return False

    def cancel_recurrence_instance(
        self,
        source: Source,
        master_todo_id: str,
        recurrence_id_str: str,
    ) -> bool:
        """Add a CANCELLED RECURRENCE-ID exception so this instance is removed from the series."""
        uid = self._resource_uid_from_todo_id(master_todo_id)
        if not uid:
            return False
        client = self._get_client(source)
        if not client:
            return False
        try:
            principal = client.principal()
            cancelled_bytes = build_cancelled_exception_vtodo(uid, recurrence_id_str)
            cancelled_cal = icalendar.Calendar.from_ical(cancelled_bytes)
            cancelled_vtodo = None
            for comp in cancelled_cal.walk():
                if comp.name == "VTODO":
                    cancelled_vtodo = comp
                    break
            if cancelled_vtodo is None:
                return False
            for cal in principal.calendars():
                todos_fn = getattr(cal, "todos", None) or getattr(cal, "get_todos", None)
                for t in (todos_fn(include_completed=True) if callable(todos_fn) else []):
                    if self._todo_ids_match(master_todo_id, t):
                        cal_inst = getattr(t, "icalendar_instance", None) or icalendar.Calendar.from_ical(
                            t.data if getattr(t, "data", None) else t.icalendar_component.to_ical()
                        )
                        if cal_inst:
                            cal_inst.add_component(cancelled_vtodo)
                            t.icalendar_instance = cal_inst
                            t.save()
                        return True
            for ts in getattr(principal, "todo_sets", lambda: [])():
                for t in (ts.todos(include_completed=True) if hasattr(ts, "todos") else []):
                    if self._todo_ids_match(master_todo_id, t):
                        cal_inst = getattr(t, "icalendar_instance", None) or icalendar.Calendar.from_ical(
                            t.data if getattr(t, "data", None) else t.icalendar_component.to_ical()
                        )
                        if cal_inst:
                            cal_inst.add_component(cancelled_vtodo)
                            t.icalendar_instance = cal_inst
                            t.save()
                        return True
        except Exception:
            pass
        return False

    def update_todo(self, source: Source, todo: Todo) -> Todo | None:
        client = self._get_client(source)
        if not client:
            raise ValueError("CalDAV connection failed (check URL and credentials)")
        master_id = todo_id_to_master_id(todo.id)
        parts = todo.id.split("::")
        recurrence_id_str = parts[-1] if (master_id and len(parts) > 1) else None
        try:
            principal = client.principal()
            for cal in principal.calendars():
                todos_fn = getattr(cal, "todos", None) or getattr(cal, "get_todos", None)
                for t in (todos_fn(include_completed=True) if callable(todos_fn) else []):
                    if not self._todo_ids_match(todo.id, t):
                        continue
                    if master_id and recurrence_id_str:
                        ical_bytes = t.data if getattr(t, "data", None) else (t.icalendar_component.to_ical() if hasattr(t, "icalendar_component") else b"")
                        if isinstance(ical_bytes, str):
                            ical_bytes = ical_bytes.encode("utf-8")
                        new_ical = merge_instance_todo_into_ical(ical_bytes, todo, recurrence_id_str)
                        t.icalendar_instance = icalendar.Calendar.from_ical(new_ical)
                        t.save()
                    else:
                        from app.services.ical_utils import todo_to_ical
                        t.icalendar_instance = icalendar.Calendar.from_ical(todo_to_ical(todo))
                        t.save()
                    return todo
            for ts in getattr(principal, "todo_sets", lambda: [])():
                for t in (ts.todos(include_completed=True) if hasattr(ts, "todos") else []):
                    if not self._todo_ids_match(todo.id, t):
                        continue
                    if master_id and recurrence_id_str:
                        ical_bytes = t.data if getattr(t, "data", None) else (t.icalendar_component.to_ical() if hasattr(t, "icalendar_component") else b"")
                        if isinstance(ical_bytes, str):
                            ical_bytes = ical_bytes.encode("utf-8")
                        new_ical = merge_instance_todo_into_ical(ical_bytes, todo, recurrence_id_str)
                        t.icalendar_instance = icalendar.Calendar.from_ical(new_ical)
                        t.save()
                    else:
                        from app.services.ical_utils import todo_to_ical
                        t.icalendar_instance = icalendar.Calendar.from_ical(todo_to_ical(todo))
                        t.save()
                    return todo
            raise ValueError("Todo not found on CalDAV server")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"CalDAV todo update failed: {e}") from e

    def delete_todo(self, source: Source, todo_id: str) -> bool:
        """Delete a todo. For recurring instance ids, we do not delete the resource; the route should call add_recurrence_exception instead."""
        master_id = todo_id_to_master_id(todo_id)
        if master_id:
            return False
        try:
            principal = self._get_client(source).principal()
            for cal in principal.calendars():
                todos_fn = getattr(cal, "todos", None) or getattr(cal, "get_todos", None)
                cal_todos = (todos_fn(include_completed=True) if callable(todos_fn) else [])
                for t in cal_todos:
                    if self._todo_ids_match(todo_id, t):
                        t.delete()
                        return True
            for ts in getattr(principal, "todo_sets", lambda: [])():
                for t in (ts.todos(include_completed=True) if hasattr(ts, "todos") else []):
                    if self._todo_ids_match(todo_id, t):
                        t.delete()
                        return True
        except Exception:
            pass
        return False
