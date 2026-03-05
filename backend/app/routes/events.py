from flask import Blueprint, request, jsonify, abort

from app.models.dtos import Event, EventCreate, EventUpdate
from app.db.sources_store import SourcesStore
from app.services.aggregator import aggregate_events_todos, get_driver, resolve_event_source


def get_sources_store() -> SourcesStore:
    return SourcesStore()


events_bp = Blueprint("events", __name__)


@events_bp.route("", methods=["GET", "POST", "PATCH", "DELETE"])
def events_handler():
    if request.method == "POST":
        return create_event()
    if request.method == "GET":
        return list_events()
    if request.method == "PATCH":
        return update_event()
    if request.method == "DELETE":
        return delete_event()
    abort(405, description="Method not allowed")


def create_event():
    data = request.get_json()
    if not data:
        abort(400, description="JSON body required")
    body = EventCreate.model_validate(data)
    store = get_sources_store()
    source = store.get_source(body.source_id)
    if not source:
        abort(404, description="Source not found")
    driver = get_driver(source.type)
    if not driver or not driver.can_write():
        abort(405, description="Source does not support creating events")
    event = Event(
        id="",
        source_id=body.source_id,
        title=body.title,
        start=body.start,
        end=body.end,
        all_day=body.all_day,
        description=body.description,
        location=body.location,
        recurrence=body.recurrence,
        url=body.url,
    )
    try:
        created = driver.create_event(source, event)
    except Exception as e:
        abort(400, description=str(e))
    if not created:
        abort(400, description="Failed to create event (check source config and permissions)")
    return jsonify(created.model_dump(mode="json")), 201


def list_events():
    start = request.args.get("start")
    end = request.args.get("end")
    id_param = request.args.get("id")
    store = get_sources_store()
    sources = store.list_sources()
    if id_param:
        event_id = id_param.strip()
        events, _, _ = aggregate_events_todos(sources)
        for e in events:
            if e.id == event_id:
                return jsonify(e.model_dump(mode="json"))
        abort(404, description="Event not found")
    events, _, _ = aggregate_events_todos(sources, start=start, end=end)
    return jsonify([e.model_dump(mode="json") for e in events])


def update_event():
    id_param = request.args.get("id")
    if not id_param:
        abort(400, description="id query parameter required")
    event_id = id_param.strip()
    data = request.get_json()
    if not data:
        abort(400, description="JSON body required")
    body = EventUpdate.model_validate(data)
    store = get_sources_store()
    sources = store.list_sources()
    resolved = resolve_event_source(sources, event_id)
    if not resolved:
        abort(404, description="Event not found or read-only")
    source, driver, current = resolved
    d = current.model_dump()
    if body.title is not None:
        d["title"] = body.title
    if body.start is not None:
        d["start"] = body.start
    if body.end is not None:
        d["end"] = body.end
    if body.all_day is not None:
        d["all_day"] = body.all_day
    if body.description is not None:
        d["description"] = body.description
    if body.location is not None:
        d["location"] = body.location
    if body.recurrence is not None:
        d["recurrence"] = body.recurrence
    if body.url is not None:
        d["url"] = body.url
    try:
        updated = driver.update_event(source, Event(**d))
    except Exception as e:
        abort(400, description=str(e))
    if not updated:
        abort(400, description="Failed to update event (check source and permissions)")
    return jsonify(updated.model_dump(mode="json"))


def delete_event():
    id_param = request.args.get("id")
    if not id_param:
        abort(400, description="id query parameter required")
    event_id = id_param.strip()
    store = get_sources_store()
    sources = store.list_sources()
    resolved = resolve_event_source(sources, event_id)
    if not resolved:
        abort(404, description="Event not found or read-only")
    source, driver, _ = resolved
    try:
        if not driver.delete_event(source, event_id):
            abort(400, description="Failed to delete event (check source and permissions)")
    except Exception as e:
        abort(400, description=str(e))
    return "", 204
