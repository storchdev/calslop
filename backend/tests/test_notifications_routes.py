import importlib


def _test_client(monkeypatch, tmp_path):
    monkeypatch.setenv("CALSLOP_DISABLE_NOTIFICATION_SCHEDULER", "1")
    monkeypatch.setenv("CALSLOP_DATA_DIR", str(tmp_path))
    import app.main

    importlib.reload(app.main)
    return app.main.app.test_client()


def test_get_notification_settings_defaults(monkeypatch, tmp_path):
    client = _test_client(monkeypatch, tmp_path)

    res = client.get("/api/notifications/settings")
    assert res.status_code == 200
    data = res.get_json()
    assert data["enabled"] is False
    assert data["target"] == "notify_send"


def test_put_notification_settings_webhook(monkeypatch, tmp_path):
    client = _test_client(monkeypatch, tmp_path)

    res = client.put(
        "/api/notifications/settings",
        json={
            "enabled": True,
            "target": "webhook",
            "webhook": {"url": "https://example.com/hook", "headers": {"X-Auth": "abc"}},
        },
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["enabled"] is True
    assert data["target"] == "webhook"
    assert data["webhook"]["url"] == "https://example.com/hook"


def test_put_notification_settings_email_requires_env(monkeypatch, tmp_path):
    client = _test_client(monkeypatch, tmp_path)

    res = client.put(
        "/api/notifications/settings",
        json={
            "enabled": True,
            "target": "email",
            "email": {"to": "user@example.com"},
        },
    )
    assert res.status_code == 400
    assert "CALSLOP_EMAIL_SMTP_HOST" in res.get_json()["detail"]


def test_post_notifications_test_uses_sender(monkeypatch, tmp_path):
    client = _test_client(monkeypatch, tmp_path)
    sent: list[tuple[str, str]] = []

    class DummySender:
        def send(self, title: str, body: str) -> None:
            sent.append((title, body))

    monkeypatch.setattr("app.routes.notifications.create_sender", lambda settings: DummySender())

    put_res = client.put(
        "/api/notifications/settings",
        json={
            "enabled": True,
            "target": "notify_send",
        },
    )
    assert put_res.status_code == 200

    test_res = client.post("/api/notifications/test", json={})
    assert test_res.status_code == 200
    assert sent
    assert sent[0][0] == "Calslop test notification"
