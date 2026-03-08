from flask import Blueprint, abort, jsonify, request

from app.models.dtos import Event, EventCreate, EventUpdate
from app.routes.utils import (
    get_sources_store,
    merge_with_partial_update,
    parse_json_body,
    require_query_param,
)
from app.services.aggregator import aggregate_events_todos, get_driver, resolve_event_source

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
    body = parse_json_body(EventCreate)
    store = get_sources_store()
    source = store.get_source(body.source_id)
    if not source:
        abort(404, description="Source not found")
    driver = get_driver(source.type)
    if not driver or not driver.can_write():
        abort(405, description="Source does not support creating events")
    event = Event(id="", **body.model_dump())
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
    event_id = require_query_param("id")
    body = parse_json_body(EventUpdate)
    store = get_sources_store()
    sources = store.list_sources()
    resolved = resolve_event_source(sources, event_id)
    if not resolved:
        abort(404, description="Event not found or read-only")
    source, driver, current = resolved
    payload = merge_with_partial_update(current, body)
    try:
        updated = driver.update_event(source, Event(**payload))
    except Exception as e:
        abort(400, description=str(e))
    if not updated:
        abort(400, description="Failed to update event (check source and permissions)")
    return jsonify(updated.model_dump(mode="json"))


def delete_event():
    event_id = require_query_param("id")
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
