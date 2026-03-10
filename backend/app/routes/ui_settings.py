from __future__ import annotations

from flask import Blueprint, jsonify

from app.db.app_config_store import AppConfigStore
from app.models.dtos import UiSettings, UiSettingsUpdate
from app.routes.utils import parse_json_body

ui_settings_bp = Blueprint("ui_settings", __name__)


def _load_settings(config_store: AppConfigStore) -> UiSettings:
    data = config_store.load()
    return UiSettings.model_validate(data.get("ui") or {})


def _save_settings(config_store: AppConfigStore, settings: UiSettings) -> None:
    data = config_store.load()
    data["ui"] = settings.model_dump(mode="json")
    config_store.save(data)


@ui_settings_bp.route("", methods=["GET"])
def get_ui_settings():
    config_store = AppConfigStore()
    settings = _load_settings(config_store)
    return jsonify(settings.model_dump(mode="json"))


@ui_settings_bp.route("", methods=["PUT"])
def update_ui_settings():
    body = parse_json_body(UiSettingsUpdate)
    config_store = AppConfigStore()
    current = _load_settings(config_store)
    merged = current.model_dump(mode="python")
    merged.update(body.model_dump(exclude_unset=True, mode="python"))
    settings = UiSettings.model_validate(merged)
    _save_settings(config_store, settings)
    return jsonify(settings.model_dump(mode="json"))
