from flask import Blueprint, request, jsonify, abort

from app.models.dtos import Todo, TodoCreate, TodoUpdate
from app.db.sources_store import SourcesStore
from app.services.aggregator import aggregate_events_todos, get_driver, resolve_todo_source
from app.services.ical_utils import todo_id_to_master_id


def get_sources_store() -> SourcesStore:
    return SourcesStore()


todos_bp = Blueprint("todos", __name__)


@todos_bp.route("", methods=["GET", "POST", "PATCH", "DELETE"])
def todos_handler():
    if request.method == "POST":
        return create_todo()
    if request.method == "GET":
        return list_todos()
    if request.method == "PATCH":
        return update_todo()
    if request.method == "DELETE":
        return delete_todo()
    abort(405, description="Method not allowed")


def create_todo():
    data = request.get_json()
    if not data:
        abort(400, description="JSON body required")
    body = TodoCreate.model_validate(data)
    store = get_sources_store()
    source = store.get_source(body.source_id)
    if not source:
        abort(404, description="Source not found")
    driver = get_driver(source.type)
    if not driver or not driver.can_write():
        abort(405, description="Source does not support creating todos")
    todo = Todo(
        id="",
        source_id=body.source_id,
        summary=body.summary,
        completed=body.completed,
        due=body.due,
        description=body.description,
        priority=body.priority,
        recurrence=body.recurrence,
    )
    try:
        created = driver.create_todo(source, todo)
    except Exception as e:
        abort(400, description=str(e))
    if not created:
        abort(400, description="Failed to create todo (check source config and permissions)")
    return jsonify(created.model_dump(mode="json")), 201


def list_todos():
    id_param = request.args.get("id")
    store = get_sources_store()
    sources = store.list_sources()
    _, todos, _ = aggregate_events_todos(sources)
    if id_param:
        todo_id = id_param.strip()
        for t in todos:
            if t.id == todo_id:
                return jsonify(t.model_dump(mode="json"))
        abort(404, description="Todo not found")
    return jsonify([t.model_dump(mode="json") for t in todos])


def update_todo():
    id_param = request.args.get("id")
    if not id_param:
        abort(400, description="id query parameter required")
    todo_id = id_param.strip()
    data = request.get_json()
    if not data:
        abort(400, description="JSON body required")
    body = TodoUpdate.model_validate(data)
    store = get_sources_store()
    sources = store.list_sources()
    resolved = resolve_todo_source(sources, todo_id)
    if not resolved:
        abort(404, description="Todo not found or read-only")
    source, driver, current = resolved

    # Completing one instance of a recurring todo: add RECURRENCE-ID exception instead of updating master.
    master_todo_id = todo_id_to_master_id(todo_id)
    if master_todo_id and body.completed is True:
        recurrence_id_str = todo_id.split("::")[-1]
        if driver.add_recurrence_exception(
            source,
            master_todo_id,
            recurrence_id_str,
            current.summary,
            current.due,
            current.description,
            current.priority,
        ):
            updated = Todo(**{**current.model_dump(), "completed": True})
            return jsonify(updated.model_dump(mode="json"))

    d = current.model_dump()
    if body.summary is not None:
        d["summary"] = body.summary
    if body.completed is not None:
        d["completed"] = body.completed
    if body.due is not None:
        d["due"] = body.due
    if body.description is not None:
        d["description"] = body.description
    if body.priority is not None:
        d["priority"] = body.priority
    if body.recurrence is not None:
        d["recurrence"] = body.recurrence
    try:
        updated = driver.update_todo(source, Todo(**d))
    except Exception as e:
        abort(400, description=str(e))
    if not updated:
        abort(400, description="Failed to update todo (check source and permissions)")
    return jsonify(updated.model_dump(mode="json"))


def delete_todo():
    id_param = request.args.get("id")
    if not id_param:
        abort(400, description="id query parameter required")
    todo_id = id_param.strip()
    store = get_sources_store()
    sources = store.list_sources()
    resolved = resolve_todo_source(sources, todo_id)
    if not resolved:
        abort(404, description="Todo not found or read-only")
    source, driver, current = resolved
    master_id = todo_id_to_master_id(todo_id)
    # Recurring todo: delete the whole series (same as non-recurring delete).
    id_to_delete = master_id if master_id else todo_id
    try:
        if not driver.delete_todo(source, id_to_delete):
            abort(400, description="Failed to delete todo (check source and permissions)")
    except Exception as e:
        abort(400, description=str(e))
    return "", 204
