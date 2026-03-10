from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, jsonify

from app.db.app_config_store import AppConfigStore
from app.models.dtos import NotificationSettings, NotificationSettingsUpdate
from app.routes.utils import parse_json_body
from app.services.notifications.scheduler import render_notification_body
from app.services.notifications.senders.factory import create_sender, validate_notification_settings

notifications_bp = Blueprint("notifications", __name__)


def _load_settings(config_store: AppConfigStore) -> NotificationSettings:
    data = config_store.load()
    return NotificationSettings.model_validate(data.get("notifications") or {})


def _save_settings(config_store: AppConfigStore, settings: NotificationSettings) -> None:
    data = config_store.load()
    data["notifications"] = settings.model_dump(mode="json")
    config_store.save(data)


@notifications_bp.route("/settings", methods=["GET"])
def get_notification_settings():
    config_store = AppConfigStore()
    settings = _load_settings(config_store)
    payload = settings.model_dump(mode="json")
    errors = validate_notification_settings(settings) if settings.enabled else []
    if errors:
        payload["health_error"] = errors[0]
    return jsonify(payload)


@notifications_bp.route("/settings", methods=["PUT"])
def update_notification_settings():
    body = parse_json_body(NotificationSettingsUpdate)
    config_store = AppConfigStore()
    current = _load_settings(config_store)
    merged = current.model_dump(mode="python")
    merged.update(body.model_dump(exclude_unset=True, mode="python"))
    settings = NotificationSettings.model_validate(merged)

    if settings.enabled:
        errors = validate_notification_settings(settings)
        if errors:
            return jsonify(detail=errors[0]), 400

    _save_settings(config_store, settings)
    return jsonify(settings.model_dump(mode="json"))


@notifications_bp.route("/test", methods=["POST"])
def send_test_notification():
    config_store = AppConfigStore()
    settings = _load_settings(config_store)
    errors = validate_notification_settings(settings)
    if errors:
        return jsonify(detail=errors[0]), 400

    sender = create_sender(settings)
    now_dt = datetime.now(UTC)
    now_ms = int(now_dt.timestamp() * 1000)
    body = render_notification_body(
        title="Calslop test notification",
        kind="test",
        target_dt=now_dt,
        now_ms=now_ms,
        time_format=settings.time_format,
        body_template=settings.body_template,
    )
    sender.send("Calslop test notification", body)
    return jsonify(ok=True)
