import uuid
from pathlib import Path

from app.models.dtos import Event, Source, Todo
from app.services.ical_utils import (
    parse_events_from_ical,
    parse_todos_from_ical,
    event_to_ical,
    todo_to_ical,
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
        for ics_file in path.glob("*.ics"):
            try:
                text = ics_file.read_text(encoding="utf-8", errors="replace")
                # Use file path as part of id for local: source_id + path stem + uid from file
                file_source_id = f"{source.id}::{ics_file.stem}"
                events = parse_events_from_ical(text, file_source_id)
                todos = parse_todos_from_ical(text, file_source_id)
                all_events.extend(events)
                all_todos.extend(todos)
            except Exception as e:
                errors.append(f"{ics_file.name}: {e}")
        if start and end:
            from datetime import datetime
            try:
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                if hasattr(start_dt, "tzinfo") and start_dt.tzinfo:
                    start_dt = start_dt.replace(tzinfo=None)
                if hasattr(end_dt, "tzinfo") and end_dt.tzinfo:
                    end_dt = end_dt.replace(tzinfo=None)
                all_events = [e for e in all_events if e.end >= start_dt and e.start <= end_dt]
            except (ValueError, TypeError):
                pass
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

    def create_event(self, source: Source, event: Event) -> Event | None:
        path_str = source.config.get("path")
        if not path_str:
            return None
        path = Path(path_str)
        if not path.is_dir():
            return None
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
            url=event.url,
        )
        ics_path = path / f"{stem}.ics"
        ics_path.write_bytes(event_to_ical(new_event))
        return new_event

    def update_event(self, source: Source, event: Event) -> Event | None:
        res = self._path_and_stem(source, event.id)
        if not res:
            return None
        path, stem = res
        ics_path = path / f"{stem}.ics"
        if not ics_path.exists():
            return None
        ics_path.write_bytes(event_to_ical(event))
        return event

    def delete_event(self, source: Source, event_id: str) -> bool:
        res = self._path_and_stem(source, event_id)
        if not res:
            return False
        path, stem = res
        ics_path = path / f"{stem}.ics"
        if ics_path.exists():
            ics_path.unlink()
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
        )
        ics_path = path / f"{stem}.ics"
        ics_path.write_bytes(todo_to_ical(new_todo))
        return new_todo

    def update_todo(self, source: Source, todo: Todo) -> Todo | None:
        parts = todo.id.split("::")
        if len(parts) < 2:
            return None
        stem = parts[1]  # file stem e.g. todo_abc123
        path_str = source.config.get("path")
        if not path_str:
            return None
        ics_path = Path(path_str) / f"{stem}.ics"
        if ics_path.exists():
            ics_path.write_bytes(todo_to_ical(todo))
            return todo
        return None

    def delete_todo(self, source: Source, todo_id: str) -> bool:
        parts = todo_id.split("::")
        if len(parts) < 2:
            return False
        stem = parts[1]
        path_str = source.config.get("path")
        if not path_str:
            return False
        ics_path = Path(path_str) / f"{stem}.ics"
        if ics_path.exists():
            ics_path.unlink()
            return True
        return False
