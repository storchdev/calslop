from litestar import Controller, get, post, patch, delete
from litestar.exceptions import NotFoundException, MethodNotAllowedException
from litestar.params import Parameter

from app.models.dtos import Event, EventCreate, EventUpdate
from app.db.sources_store import SourcesStore
from app.services.aggregator import aggregate_events_todos, get_driver, resolve_event_source


def get_sources_store() -> SourcesStore:
    return SourcesStore()


class EventsController(Controller):
    path = "/api/events"

    @get()
    async def list_events(
        self,
        start: str | None = Parameter(default=None),
        end: str | None = Parameter(default=None),
    ) -> list[Event]:
        store = get_sources_store()
        sources = store.list_sources()
        events, _, _ = aggregate_events_todos(sources, start=start, end=end)
        return events

    @get("/{event_id:path}")
    async def get_event(self, event_id: str) -> Event:
        store = get_sources_store()
        sources = store.list_sources()
        events, _, _ = aggregate_events_todos(sources)
        for e in events:
            if e.id == event_id:
                return e
        raise NotFoundException(detail="Event not found")

    @post()
    async def create_event(self, data: EventCreate) -> Event:
        store = get_sources_store()
        source = store.get_source(data.source_id)
        if not source:
            raise NotFoundException(detail="Source not found")
        driver = get_driver(source.type)
        if not driver or not driver.can_write():
            raise MethodNotAllowedException(detail="Source does not support creating events")
        event = Event(
            id="",
            source_id=data.source_id,
            title=data.title,
            start=data.start,
            end=data.end,
            all_day=data.all_day,
            description=data.description,
            location=data.location,
            recurrence=data.recurrence,
            url=data.url,
        )
        created = driver.create_event(source, event)
        if not created:
            raise MethodNotAllowedException(detail="Failed to create event")
        return created

    @patch("/{event_id:path}")
    async def update_event(self, event_id: str, data: EventUpdate) -> Event:
        store = get_sources_store()
        sources = store.list_sources()
        resolved = resolve_event_source(sources, event_id)
        if not resolved:
            raise NotFoundException(detail="Event not found or read-only")
        source, driver, current = resolved
        d = current.model_dump()
        if data.title is not None:
            d["title"] = data.title
        if data.start is not None:
            d["start"] = data.start
        if data.end is not None:
            d["end"] = data.end
        if data.all_day is not None:
            d["all_day"] = data.all_day
        if data.description is not None:
            d["description"] = data.description
        if data.location is not None:
            d["location"] = data.location
        if data.recurrence is not None:
            d["recurrence"] = data.recurrence
        if data.url is not None:
            d["url"] = data.url
        updated = driver.update_event(source, Event(**d))
        if not updated:
            raise MethodNotAllowedException(detail="Failed to update event")
        return updated

    @delete("/{event_id:path}")
    async def delete_event(self, event_id: str) -> None:
        store = get_sources_store()
        sources = store.list_sources()
        resolved = resolve_event_source(sources, event_id)
        if not resolved:
            raise NotFoundException(detail="Event not found or read-only")
        source, driver, _ = resolved
        if not driver.delete_event(source, event_id):
            raise MethodNotAllowedException(detail="Failed to delete event")
