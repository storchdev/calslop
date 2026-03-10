import json

from app.db.app_config_store import AppConfigStore


def test_app_config_store_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    store = AppConfigStore(path)

    payload = {
        "sources": [{"id": "a", "type": "ics_url", "name": "A", "enabled": True, "config": {}}],
        "notifications": {"enabled": True, "target": "notify_send"},
        "future_key": {"x": 1},
    }
    store.save(payload)

    loaded = store.load()
    assert loaded == payload
    assert json.loads(path.read_text())["future_key"] == {"x": 1}


def test_app_config_store_returns_empty_dict_on_invalid_json(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json}")
    store = AppConfigStore(path)

    assert store.load() == {}
