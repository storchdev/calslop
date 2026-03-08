from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, jsonify, request
from pydantic import BaseModel

from app.models.dtos import Source, Todo, TodoCreate, TodoUpdate
from app.routes.utils import (
    get_sources_store,
    merge_with_partial_update,
    parse_json_body,
    require_query_param,
)
from app.services.aggregator import aggregate_events_todos, get_driver, resolve_todo_source
from app.services.ical_utils import next_recurrence_occurrence, todo_id_to_master_id

todos_bp = Blueprint("todos", __name__)


def _todo_to_json(todo: Todo) -> dict:
    payload = todo.model_dump(mode="json")
    if todo.due is None:
        return payload
    due = todo.due
    due_utc = due.replace(tzinfo=timezone.utc) if due.tzinfo is None else due.astimezone(timezone.utc)
    payload["due"] = due_utc.isoformat().replace("+00:00", "Z")
    return payload


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


class BulkPushBody(BaseModel):
    start: datetime | None = None
    end: datetime | None = None
    days: int
    overdue_only: bool = False


@todos_bp.route("/bulk/push", methods=["POST"])
def bulk_push_todos():
    body = parse_json_body(BulkPushBody)

    start_ts = body.start
    end_ts = body.end
    if not body.overdue_only:
        if start_ts is None or end_ts is None:
            abort(400, description="start and end are required unless overdue_only is true")
        if end_ts < start_ts:
            abort(400, description="end must be on or after start")

    store = get_sources_store()
    sources = store.list_sources()
    updated = 0
    failed: list[dict[str, str]] = []
    now_epoch = datetime.now().timestamp()
    start_epoch = start_ts.timestamp() if start_ts else None
    end_epoch = end_ts.timestamp() if end_ts else None

    source_by_id = {s.id: s for s in sources if s.enabled}
    writable_driver_by_source_id = {}
    for source_id, source in source_by_id.items():
        driver = get_driver(source.type)
        if driver and driver.can_write():
            writable_driver_by_source_id[source_id] = driver

    _, candidate_todos, _ = aggregate_events_todos(sources)
    candidate_ids: list[str] = []
    for todo in candidate_todos:
        if todo.completed:
            continue
        if todo.due is None:
            continue
        due_epoch = todo.due.timestamp()
        if body.overdue_only:
            if due_epoch >= now_epoch:
                continue
        else:
            if start_epoch is None or end_epoch is None:
                continue
            if due_epoch < start_epoch or due_epoch > end_epoch:
                continue
        candidate_ids.append(todo.id)

    todo_ids_by_source_id: dict[str, list[str]] = {}
    for todo_id in candidate_ids:
        source_id = todo_id.split("::", 1)[0]
        if source_id not in writable_driver_by_source_id:
            failed.append({"id": todo_id, "error": "Todo not found or read-only"})
            continue
        if source_id not in todo_ids_by_source_id:
            todo_ids_by_source_id[source_id] = []
        todo_ids_by_source_id[source_id].append(todo_id)

    def _update_one(source: Source, todo: Todo, days: int):
        # Intentionally create a fresh driver per task to avoid shared mutable state.
        driver = get_driver(source.type)
        if not driver or not driver.can_write():
            return False, "Todo not found or read-only"
        shifted_due = todo.due + timedelta(days=days) if todo.due else None
        payload = Todo(
            **{
                **todo.model_dump(),
                "due": shifted_due,
            }
        )
        try:
            ok = driver.update_todo(source, payload)
            return (True, None) if ok else (False, "Update failed")
        except Exception as e:
            return False, str(e)

    for source_id, ids in todo_ids_by_source_id.items():
        source = source_by_id.get(source_id)
        driver = writable_driver_by_source_id.get(source_id)
        if not source or not driver:
            for todo_id in ids:
                failed.append({"id": todo_id, "error": "Todo not found or read-only"})
            continue

        _, source_todos, _ = aggregate_events_todos([source])
        source_todo_map = {t.id: t for t in source_todos}

        tasks: list[tuple[str, Todo]] = []
        for todo_id in ids:
            current = source_todo_map.get(todo_id)
            if not current:
                failed.append({"id": todo_id, "error": "Todo not found or read-only"})
                continue
            tasks.append((todo_id, current))

        if not tasks:
            continue

        max_workers = max(1, min(12, len(tasks)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_todo_id = {
                executor.submit(_update_one, source, current, body.days): todo_id
                for todo_id, current in tasks
            }
            for future in as_completed(future_to_todo_id):
                todo_id = future_to_todo_id[future]
                ok, err = future.result()
                if ok:
                    updated += 1
                else:
                    failed.append({"id": todo_id, "error": err or "Update failed"})

    return jsonify({"updated": updated, "failed": failed})


def create_todo():
    body = parse_json_body(TodoCreate)
    store = get_sources_store()
    source = store.get_source(body.source_id)
    if not source:
        abort(404, description="Source not found")
    driver = get_driver(source.type)
    if not driver or not driver.can_write():
        abort(405, description="Source does not support creating todos")
    todo = Todo(id="", **body.model_dump())
    try:
        created = driver.create_todo(source, todo)
    except Exception as e:
        abort(400, description=str(e))
    if not created:
        abort(400, description="Failed to create todo (check source config and permissions)")
    return jsonify(_todo_to_json(created)), 201


def list_todos():
    id_param = request.args.get("id")
    store = get_sources_store()
    sources = store.list_sources()
    _, todos, _ = aggregate_events_todos(sources)
    if id_param:
        todo_id = id_param.strip()
        for t in todos:
            if t.id == todo_id:
                return jsonify(_todo_to_json(t))
        abort(404, description="Todo not found")
    return jsonify([_todo_to_json(t) for t in todos])


def update_todo():
    todo_id = require_query_param("id")
    body = parse_json_body(TodoUpdate)
    store = get_sources_store()
    sources = store.list_sources()
    resolved = resolve_todo_source(sources, todo_id)
    if not resolved:
        abort(404, description="Todo not found or read-only")
    source, driver, current = resolved

    # Completing one instance of a recurring todo: mirror iOS Reminders behavior.
    # Advance the recurring master to the next occurrence and create a separate
    # completed non-recurring todo for the completed instance.
    master_todo_id = todo_id_to_master_id(todo_id)
    if master_todo_id and body.completed is True:
        recurrence = current.recurrence or ""
        next_due = next_recurrence_occurrence(recurrence, current.due)
        if next_due is not None:
            try:
                master_updated = driver.update_todo(
                    source,
                    Todo(
                        id=master_todo_id,
                        source_id=current.source_id,
                        summary=current.summary,
                        completed=False,
                        due=next_due,
                        description=current.description,
                        priority=current.priority,
                        recurrence=recurrence,
                        alert_minutes_before=current.alert_minutes_before,
                    ),
                )
                completed_created = driver.create_todo(
                    source,
                    Todo(
                        id="",
                        source_id=current.source_id,
                        summary=current.summary,
                        completed=True,
                        due=current.due,
                        description=current.description,
                        priority=current.priority,
                        recurrence=None,
                        alert_minutes_before=current.alert_minutes_before,
                    ),
                )
                if master_updated and completed_created:
                    updated = Todo(
                        **{**current.model_dump(), "completed": True, "recurrence": None}
                    )
                    return jsonify(_todo_to_json(updated))
            except Exception:
                pass

        # Fallback for sources that cannot create detached completions.
        recurrence_id_str = todo_id.split("::")[-1]
        if driver.add_recurrence_exception(
            source,
            master_todo_id,
            recurrence_id_str,
            current.summary,
            current.due,
            current.description,
            current.priority,
            current.alert_minutes_before,
        ):
            updated = Todo(**{**current.model_dump(), "completed": True, "recurrence": None})
            return jsonify(_todo_to_json(updated))

    payload = merge_with_partial_update(current, body)
    try:
        updated = driver.update_todo(source, Todo(**payload))
    except Exception as e:
        abort(400, description=str(e))
    if not updated:
        abort(400, description="Failed to update todo (check source and permissions)")
    return jsonify(_todo_to_json(updated))


def delete_todo():
    todo_id = require_query_param("id")
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
