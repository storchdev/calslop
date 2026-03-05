from datetime import datetime

import caldav
from caldav.elements import dav

from app.models.dtos import Event, Source, Todo
from app.services.ical_utils import parse_events_from_ical, parse_todos_from_ical
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
                    # Some servers put todos in calendars
                    for cal in principal.calendars():
                        try:
                            todos_fetched = getattr(cal, "todos", lambda: [])()
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
                            todos_fetched = ts.todos()
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
            return None
        try:
            principal = client.principal()
            calendars = principal.calendars()
            if not calendars:
                return None
            cal = calendars[0]
            from app.services.ical_utils import event_to_ical
            ical_str = event_to_ical(event).decode("utf-8")
            new_ev = cal.save_event(ical_str)
            if new_ev and hasattr(new_ev, "id"):
                event = Event(**{**event.model_dump(), "id": f"{source.id}::{getattr(new_ev, 'id', event.id)}"})
            return event
        except Exception:
            return None

    def update_event(self, source: Source, event: Event) -> Event | None:
        # CalDAV update: fetch event by id, save back with new data
        try:
            principal = self._get_client(source).principal()
            for cal in principal.calendars():
                events = cal.events()
                for ev in events:
                    if hasattr(ev, "id") and event.id.endswith(str(ev.id)):
                        from app.services.ical_utils import event_to_ical
                        ev.save(icalendar=event_to_ical(event).decode("utf-8"))
                        return event
        except Exception:
            pass
        return None

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
        try:
            principal = self._get_client(source).principal()
            todo_sets = getattr(principal, "todo_sets", lambda: [])()
            if todo_sets:
                ts = todo_sets[0]
                from app.services.ical_utils import todo_to_ical
                ical_str = todo_to_ical(todo).decode("utf-8")
                ts.save_todo(ical_str)
                return todo
        except Exception:
            pass
        return None

    def update_todo(self, source: Source, todo: Todo) -> Todo | None:
        try:
            principal = self._get_client(source).principal()
            for cal in principal.calendars():
                for t in getattr(cal, "todos", lambda: [])():
                    if todo.id in str(getattr(t, "id", "")):
                        from app.services.ical_utils import todo_to_ical
                        t.save(icalendar=todo_to_ical(todo).decode("utf-8"))
                        return todo
        except Exception:
            pass
        return None

    def delete_todo(self, source: Source, todo_id: str) -> bool:
        try:
            principal = self._get_client(source).principal()
            for cal in principal.calendars():
                for t in getattr(cal, "todos", lambda: [])():
                    if todo_id in str(getattr(t, "id", "")):
                        t.delete()
                        return True
        except Exception:
            pass
        return False
