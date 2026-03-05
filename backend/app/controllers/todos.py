from litestar import Controller, get, post, patch, delete
from litestar.exceptions import NotFoundException, MethodNotAllowedException

from app.models.dtos import Todo, TodoCreate, TodoUpdate
from app.db.sources_store import SourcesStore
from app.services.aggregator import aggregate_events_todos, get_driver, resolve_todo_source


def get_sources_store() -> SourcesStore:
    return SourcesStore()


class TodosController(Controller):
    path = "/api/todos"

    @get()
    async def list_todos(self) -> list[Todo]:
        store = get_sources_store()
        sources = store.list_sources()
        _, todos, _ = aggregate_events_todos(sources)
        return todos

    @get("/{todo_id:path}")
    async def get_todo(self, todo_id: str) -> Todo:
        store = get_sources_store()
        sources = store.list_sources()
        _, todos, _ = aggregate_events_todos(sources)
        for t in todos:
            if t.id == todo_id:
                return t
        raise NotFoundException(detail="Todo not found")

    @post()
    async def create_todo(self, data: TodoCreate) -> Todo:
        store = get_sources_store()
        source = store.get_source(data.source_id)
        if not source:
            raise NotFoundException(detail="Source not found")
        driver = get_driver(source.type)
        if not driver or not driver.can_write():
            raise MethodNotAllowedException(detail="Source does not support creating todos")
        todo = Todo(
            id="",
            source_id=data.source_id,
            summary=data.summary,
            completed=data.completed,
            due=data.due,
            description=data.description,
            priority=data.priority,
            recurrence=data.recurrence,
        )
        created = driver.create_todo(source, todo)
        if not created:
            raise MethodNotAllowedException(detail="Failed to create todo")
        return created

    @patch("/{todo_id:path}")
    async def update_todo(self, todo_id: str, data: TodoUpdate) -> Todo:
        store = get_sources_store()
        sources = store.list_sources()
        resolved = resolve_todo_source(sources, todo_id)
        if not resolved:
            raise NotFoundException(detail="Todo not found or read-only")
        source, driver, current = resolved
        d = current.model_dump()
        if data.summary is not None:
            d["summary"] = data.summary
        if data.completed is not None:
            d["completed"] = data.completed
        if data.due is not None:
            d["due"] = data.due
        if data.description is not None:
            d["description"] = data.description
        if data.priority is not None:
            d["priority"] = data.priority
        if data.recurrence is not None:
            d["recurrence"] = data.recurrence
        updated = driver.update_todo(source, Todo(**d))
        if not updated:
            raise MethodNotAllowedException(detail="Failed to update todo")
        return updated

    @delete("/{todo_id:path}")
    async def delete_todo(self, todo_id: str) -> None:
        store = get_sources_store()
        sources = store.list_sources()
        resolved = resolve_todo_source(sources, todo_id)
        if not resolved:
            raise NotFoundException(detail="Todo not found or read-only")
        source, driver, _ = resolved
        if not driver.delete_todo(source, todo_id):
            raise MethodNotAllowedException(detail="Failed to delete todo")
