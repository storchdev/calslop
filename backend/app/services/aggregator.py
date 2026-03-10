from app.models.dtos import Event, Source, Todo
from app.services.sources import CalDAVDriver, IcsUrlDriver, LocalFolderDriver
from app.services.sources.base import SourceDriver


def get_driver(source_type: str) -> SourceDriver | None:
    if source_type == "ics_url":
        return IcsUrlDriver()
    if source_type == "local_folder":
        return LocalFolderDriver()
    if source_type == "caldav":
        return CalDAVDriver()
    return None


def _source_id_from_aggregate_id(aggregate_id: str) -> str | None:
    """Extract source id (first segment) from event/todo id like 'source_id::...'."""
    parts = aggregate_id.split("::", 1)
    return parts[0] if len(parts) >= 1 else None


def _resolve_source_and_driver(
    sources: list[Source],
    item_id: str,
) -> tuple[Source, SourceDriver] | None:
    source_id = _source_id_from_aggregate_id(item_id)
    if not source_id:
        return None

    source = next((s for s in sources if s.id == source_id), None)
    if not source:
        return None

    driver = get_driver(source.type)
    if not driver or not driver.can_write():
        return None
    return source, driver


def resolve_event_source(
    sources: list[Source], event_id: str
) -> tuple[Source, SourceDriver, Event] | None:
    """Find source, driver, and current event for event_id."""
    resolved = _resolve_source_and_driver(sources, event_id)
    if not resolved:
        return None
    source, driver = resolved
    event = driver.get_event(source, event_id)
    return (source, driver, event) if event else None


def resolve_todo_source(
    sources: list[Source], todo_id: str
) -> tuple[Source, SourceDriver, Todo] | None:
    """Find source, driver, and current todo for todo_id."""
    resolved = _resolve_source_and_driver(sources, todo_id)
    if not resolved:
        return None
    source, driver = resolved
    todo = driver.get_todo(source, todo_id)
    return (source, driver, todo) if todo else None


def aggregate_events_todos(
    sources: list[Source],
    start: str | None = None,
    end: str | None = None,
) -> tuple[list[Event], list[Todo], list[str]]:
    """Fetch from all enabled sources and merge events and todos."""
    all_events: list[Event] = []
    all_todos: list[Todo] = []
    all_errors: list[str] = []
    for source in sources:
        if not source.enabled:
            continue
        driver = get_driver(source.type)
        if not driver:
            all_errors.append(f"Unknown source type: {source.type}")
            continue
        result = driver.fetch(source, start=start, end=end)
        all_events.extend(result.events)
        all_todos.extend(result.todos)
        all_errors.extend(result.errors)
    return all_events, all_todos, all_errors
