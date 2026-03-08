from flask import Blueprint, abort, jsonify

from app.models.dtos import SourceCreate, SourceUpdate
from app.routes.utils import get_sources_store, parse_json_body

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
    body = parse_json_body(SourceCreate)
    store = get_sources_store()
    source = store.add_source(body)
    return jsonify(source.model_dump(mode="json")), 201


@sources_bp.route("/<path:source_id>", methods=["PUT"])
def update_source(source_id: str):
    body = parse_json_body(SourceUpdate)
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
