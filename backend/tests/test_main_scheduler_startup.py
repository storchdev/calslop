import importlib


def _reload_main():
    import app.main

    importlib.reload(app.main)


def test_scheduler_does_not_start_in_reloader_parent(monkeypatch, tmp_path):
    started: list[bool] = []

    def fake_start(self) -> None:
        started.append(True)

    monkeypatch.setenv("CALSLOP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASK_RUN_FROM_CLI", "true")
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    monkeypatch.delenv("CALSLOP_DISABLE_NOTIFICATION_SCHEDULER", raising=False)
    monkeypatch.setattr(
        "app.services.notifications.scheduler.NotificationScheduler.start", fake_start
    )

    _reload_main()

    assert started == []


def test_scheduler_starts_in_reloader_child(monkeypatch, tmp_path):
    started: list[bool] = []

    def fake_start(self) -> None:
        started.append(True)

    monkeypatch.setenv("CALSLOP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASK_RUN_FROM_CLI", "true")
    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")
    monkeypatch.delenv("CALSLOP_DISABLE_NOTIFICATION_SCHEDULER", raising=False)
    monkeypatch.setattr(
        "app.services.notifications.scheduler.NotificationScheduler.start", fake_start
    )

    _reload_main()

    assert len(started) == 1


def test_scheduler_does_not_start_when_disabled(monkeypatch, tmp_path):
    started: list[bool] = []

    def fake_start(self) -> None:
        started.append(True)

    monkeypatch.setenv("CALSLOP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CALSLOP_DISABLE_NOTIFICATION_SCHEDULER", "1")
    monkeypatch.delenv("FLASK_RUN_FROM_CLI", raising=False)
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    monkeypatch.setattr(
        "app.services.notifications.scheduler.NotificationScheduler.start", fake_start
    )

    _reload_main()

    assert started == []
