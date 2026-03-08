from __future__ import annotations

from typing import Any, TypeVar

from flask import abort, request
from pydantic import BaseModel

from app.db.sources_store import SourcesStore

ModelT = TypeVar("ModelT", bound=BaseModel)


def get_sources_store() -> SourcesStore:
    return SourcesStore()


def parse_json_body(model_type: type[ModelT]) -> ModelT:
    data = request.get_json()
    if not data:
        abort(400, description="JSON body required")
    return model_type.model_validate(data)


def require_query_param(name: str) -> str:
    value = request.args.get(name)
    if value is None or not value.strip():
        abort(400, description=f"{name} query parameter required")
    return value.strip()


def merge_with_partial_update(current: BaseModel, patch: BaseModel) -> dict[str, Any]:
    payload = current.model_dump()
    payload.update(patch.model_dump(exclude_unset=True))
    return payload
