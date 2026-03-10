import importlib
import json


def _test_client(monkeypatch, tmp_path):
    monkeypatch.setenv("CALSLOP_DISABLE_NOTIFICATION_SCHEDULER", "1")
    monkeypatch.setenv("CALSLOP_DATA_DIR", str(tmp_path))
    import app.main

    importlib.reload(app.main)
    return app.main.app.test_client()


def test_get_ui_settings_defaults(monkeypatch, tmp_path):
    client = _test_client(monkeypatch, tmp_path)

    res = client.get("/api/ui/settings")
    assert res.status_code == 200
    assert res.get_json() == {
        "auto_sync_interval": "off",
        "time_display_format": "24h",
    }


def test_put_ui_settings_persists(monkeypatch, tmp_path):
    client = _test_client(monkeypatch, tmp_path)

    res = client.put(
        "/api/ui/settings",
        json={
            "auto_sync_interval": "1m",
            "time_display_format": "12h",
        },
    )
    assert res.status_code == 200
    assert res.get_json() == {
        "auto_sync_interval": "1m",
        "time_display_format": "12h",
    }

    get_res = client.get("/api/ui/settings")
    assert get_res.status_code == 200
    assert get_res.get_json() == {
        "auto_sync_interval": "1m",
        "time_display_format": "12h",
    }


def test_put_ui_settings_preserves_other_sections(monkeypatch, tmp_path):
    client = _test_client(monkeypatch, tmp_path)
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"notifications": {"enabled": True}}))

    res = client.put("/api/ui/settings", json={"auto_sync_interval": "30s"})
    assert res.status_code == 200

    saved = json.loads(path.read_text())
    assert saved["notifications"] == {"enabled": True}
    assert saved["ui"]["auto_sync_interval"] == "30s"
    assert saved["ui"]["time_display_format"] == "24h"
