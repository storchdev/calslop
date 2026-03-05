from flask import Blueprint, request, jsonify, abort

from app.models.dtos import Source, SourceCreate, SourceUpdate
from app.db.sources_store import SourcesStore


def get_sources_store() -> SourcesStore:
    return SourcesStore()


sources_bp = Blueprint("sources", __name__)


@sources_bp.route("", methods=["GET"])
def list_sources():
    store = get_sources_store()
    return jsonify([s.model_dump(mode="json") for s in store.list_sources()])


@sources_bp.route("/<path:source_id>", methods=["GET"])
def get_source(source_id: str):
    store = get_sources_store()
    s = store.get_source(source_id)
    if not s:
        abort(404, description="Source not found")
    return jsonify(s.model_dump(mode="json"))


@sources_bp.route("", methods=["POST"])
def create_source():
    data = request.get_json()
    if not data:
        abort(400, description="JSON body required")
    body = SourceCreate.model_validate(data)
    store = get_sources_store()
    source = store.add_source(body)
    return jsonify(source.model_dump(mode="json")), 201


@sources_bp.route("/<path:source_id>", methods=["PUT"])
def update_source(source_id: str):
    data = request.get_json()
    if not data:
        abort(400, description="JSON body required")
    body = SourceUpdate.model_validate(data)
    store = get_sources_store()
    s = store.update_source(source_id, body)
    if not s:
        abort(404, description="Source not found")
    return jsonify(s.model_dump(mode="json"))


@sources_bp.route("/<path:source_id>", methods=["DELETE"])
def delete_source(source_id: str):
    store = get_sources_store()
    if not store.delete_source(source_id):
        abort(404, description="Source not found")
    return "", 204
