import uuid
from pathlib import Path

import icalendar

from app.models.dtos import Event, Source, Todo
from app.services.ical_cache import invalidate_source_cache, parse_events_cached, parse_todos_cached
from app.services.ical_recurrence import parse_iso_window
from app.services.ical_utils import (
    event_to_ical,
    todo_to_ical,
    build_exception_vtodo,
    build_cancelled_exception_vtodo,
    todo_id_to_master_id,
    is_recurrence_id_str,
    merge_instance_todo_into_ical,
    _update_master_vtodo_metadata,
)
from app.services.sources.base import FetchResult, SourceDriver


class LocalFolderDriver(SourceDriver):
    """Local folder of .ics files; each file can contain events and/or todos. Supports write."""

    def fetch(
        self,
        source: Source,
        start: str | None = None,
        end: str | None = None,
    ) -> FetchResult:
        path_str = source.config.get("path")
        if not path_str:
            return FetchResult([], [], errors=["Missing path in config"])
        path = Path(path_str)
        if not path.is_dir():
            return FetchResult([], [], errors=[f"Path is not a directory: {path_str}"])
        all_events: list[Event] = []
        all_todos: list[Todo] = []
        errors: list[str] = []
        window_start, window_end = parse_iso_window(start, end)
        for ics_file in path.glob("*.ics"):
            try:
                text = ics_file.read_text(encoding="utf-8", errors="replace")
                # Use file path as part of id for local: source_id + path stem + uid from file
                file_source_id = f"{source.id}::{ics_file.stem}"
                stat = ics_file.stat()
                fingerprint = f"mtime_ns:{stat.st_mtime_ns}|size:{stat.st_size}"
                events = parse_events_cached(
                    text,
                    file_source_id,
                    window_start=window_start,
                    window_end=window_end,
                    fingerprint=fingerprint,
                )
                todos = parse_todos_cached(
                    text,
                    file_source_id,
                    window_start=window_start,
                    window_end=window_end,
                    fingerprint=fingerprint,
                )
                all_events.extend(events)
                all_todos.extend(todos)
            except Exception as e:
                errors.append(f"{ics_file.name}: {e}")
        return FetchResult(events=all_events, todos=all_todos, errors=errors or None)

    def can_write(self) -> bool:
        return True

    def _path_and_stem(self, source: Source, event_id: str) -> tuple[Path, str] | None:
        path_str = source.config.get("path")
        if not path_str:
            return None
        path = Path(path_str)
        parts = event_id.split("::")
        if len(parts) >= 2:
            stem = parts[1]
            return path, stem
        return None

    def _parse_single_file(self, source: Source, item_id: str) -> tuple[list[Event], list[Todo]]:
        res = self._path_and_stem(source, item_id)
        if not res:
            return [], []
        path, stem = res
        ics_path = path / f"{stem}.ics"
        if not ics_path.exists() or not ics_path.is_file():
            return [], []
        text = ics_path.read_text(encoding="utf-8", errors="replace")
        file_source_id = f"{source.id}::{stem}"
        stat = ics_path.stat()
        fingerprint = f"mtime_ns:{stat.st_mtime_ns}|size:{stat.st_size}"
        events = parse_events_cached(
            text,
            file_source_id,
            window_start=None,
            window_end=None,
            fingerprint=fingerprint,
        )
        todos = parse_todos_cached(
            text,
            file_source_id,
            window_start=None,
            window_end=None,
            fingerprint=fingerprint,
        )
        return events, todos

    def get_event(self, source: Source, event_id: str) -> Event | None:
        events, _ = self._parse_single_file(source, event_id)
        return next((event for event in events if event.id == event_id), None)

    def get_todo(self, source: Source, todo_id: str) -> Todo | None:
        _, todos = self._parse_single_file(source, todo_id)
        return next((todo for todo in todos if todo.id == todo_id), None)

    def create_event(self, source: Source, event: Event) -> Event | None:
        path_str = source.config.get("path")
        if not path_str:
            raise ValueError("Missing path in source config")
        path = Path(path_str)
        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {path_str}")
        stem = uuid.uuid4().hex
        uid = stem
        event_id = f"{source.id}::{stem}::{uid}"
        new_event = Event(
            id=event_id,
            source_id=f"{source.id}::{stem}",
            title=event.title,
            start=event.start,
            end=event.end,
            all_day=event.all_day,
            description=event.description,
            location=event.location,
            recurrence=event.recurrence,
            url=event.url,
        )
        ics_path = path / f"{stem}.ics"
        ics_path.write_bytes(event_to_ical(new_event))
        invalidate_source_cache(source.id)
        return new_event

    def update_event(self, source: Source, event: Event) -> Event | None:
        res = self._path_and_stem(source, event.id)
        if not res:
            raise ValueError("Invalid event id for local source")
        path, stem = res
        ics_path = path / f"{stem}.ics"
        if not ics_path.exists():
            raise ValueError(f"Event file not found: {stem}.ics")
        ics_path.write_bytes(event_to_ical(event))
        invalidate_source_cache(source.id)
        return event

    def delete_event(self, source: Source, event_id: str) -> bool:
        res = self._path_and_stem(source, event_id)
        if not res:
            return False
        path, stem = res
        ics_path = path / f"{stem}.ics"
        if ics_path.exists():
            ics_path.unlink()
            invalidate_source_cache(source.id)
            return True
        return False

    def create_todo(self, source: Source, todo: Todo) -> Todo | None:
        path_str = source.config.get("path")
        if not path_str:
            return None
        path = Path(path_str)
        if not path.is_dir():
            return None
        stem = f"todo_{uuid.uuid4().hex}"
        uid = stem
        todo_id = f"{source.id}::{stem}::{uid}"
        new_todo = Todo(
            id=todo_id,
            source_id=f"{source.id}::{stem}",
            summary=todo.summary,
            completed=todo.completed,
            due=todo.due,
            description=todo.description,
            priority=todo.priority,
            recurrence=getattr(todo, "recurrence", None),
        )
        ics_path = path / f"{stem}.ics"
        ics_path.write_bytes(todo_to_ical(new_todo))
        invalidate_source_cache(source.id)
        return new_todo

    def update_todo(self, source: Source, todo: Todo) -> Todo | None:
        parts = todo.id.split("::")
        if len(parts) < 2:
            raise ValueError("Invalid todo id for local source")
        stem = parts[1]
        path_str = source.config.get("path")
        if not path_str:
            raise ValueError("Missing path in source config")
        ics_path = Path(path_str) / f"{stem}.ics"
        if not ics_path.exists():
            raise ValueError(f"Todo file not found: {stem}.ics")
        master_id = todo_id_to_master_id(todo.id)
        if master_id and len(parts) >= 2 and is_recurrence_id_str(parts[-1]):
            recurrence_id_str = parts[-1]
            existing = ics_path.read_bytes()
            new_ical = merge_instance_todo_into_ical(existing, todo, recurrence_id_str)
            ics_path.write_bytes(new_ical)
        else:
            ics_path.write_bytes(todo_to_ical(todo))
        invalidate_source_cache(source.id)
        return todo

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
        parts = master_todo_id.split("::")
        if len(parts) < 3:
            return False
        stem = parts[1]
        uid = parts[2]
        path_str = source.config.get("path")
        if not path_str:
            return False
        ics_path = Path(path_str) / f"{stem}.ics"
        if not ics_path.exists():
            return False
        try:
            existing = ics_path.read_bytes()
            cal = icalendar.Calendar.from_ical(existing)
            if not cal:
                return False
            exc_bytes = build_exception_vtodo(
                uid, recurrence_id_str, summary, due, description, priority, alert_minutes_before
            )
            exc_cal = icalendar.Calendar.from_ical(exc_bytes)
            for comp in exc_cal.walk():
                if comp.name == "VTODO":
                    cal.add_component(comp)
                    break
            _update_master_vtodo_metadata(cal, uid, summary, description, priority)
            ics_path.write_bytes(cal.to_ical())
            invalidate_source_cache(source.id)
            return True
        except Exception:
            return False

    def cancel_recurrence_instance(
        self,
        source: Source,
        master_todo_id: str,
        recurrence_id_str: str,
    ) -> bool:
        """Add a CANCELLED RECURRENCE-ID exception so this instance is removed from the series."""
        parts = master_todo_id.split("::")
        if len(parts) < 3:
            return False
        stem = parts[1]
        uid = parts[2]
        path_str = source.config.get("path")
        if not path_str:
            return False
        ics_path = Path(path_str) / f"{stem}.ics"
        if not ics_path.exists():
            return False
        try:
            existing = ics_path.read_bytes()
            cal = icalendar.Calendar.from_ical(existing)
            if not cal:
                return False
            cancelled_bytes = build_cancelled_exception_vtodo(uid, recurrence_id_str)
            cancelled_cal = icalendar.Calendar.from_ical(cancelled_bytes)
            for comp in cancelled_cal.walk():
                if comp.name == "VTODO":
                    cal.add_component(comp)
                    break
            ics_path.write_bytes(cal.to_ical())
            invalidate_source_cache(source.id)
            return True
        except Exception:
            return False

    def delete_todo(self, source: Source, todo_id: str) -> bool:
        parts = todo_id.split("::")
        if len(parts) < 2:
            return False
        stem = parts[1]
        path_str = source.config.get("path")
        if not path_str:
            return False
        if todo_id_to_master_id(todo_id):
            return False
        ics_path = Path(path_str) / f"{stem}.ics"
        if ics_path.exists():
            ics_path.unlink()
            invalidate_source_cache(source.id)
            return True
        return False
