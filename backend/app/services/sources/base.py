from abc import ABC, abstractmethod

from app.models.dtos import Event, Todo, Source


class FetchResult:
    def __init__(
        self,
        events: list[Event],
        todos: list[Todo],
        errors: list[str] | None = None,
    ):
        self.events = events
        self.todos = todos
        self.errors = errors or []


class SourceDriver(ABC):
    """Base for calendar/todo source drivers."""

    @abstractmethod
    def fetch(
        self,
        source: Source,
        start: str | None = None,
        end: str | None = None,
    ) -> FetchResult:
        """Fetch events (and todos if supported) for the given source and date range."""
        ...

    def can_write(self) -> bool:
        return False

    def create_event(self, source: Source, event: Event) -> Event | None:
        return None

    def update_event(self, source: Source, event: Event) -> Event | None:
        return None

    def delete_event(self, source: Source, event_id: str) -> bool:
        return False

    def create_todo(self, source: Source, todo: Todo) -> Todo | None:
        return None

    def update_todo(self, source: Source, todo: Todo) -> Todo | None:
        return None

    def delete_todo(self, source: Source, todo_id: str) -> bool:
        return False
