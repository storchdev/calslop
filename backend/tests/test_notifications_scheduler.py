from datetime import UTC, datetime, timedelta

from app.db.app_config_store import AppConfigStore
from app.db.sources_store import SourcesStore
from app.models.dtos import Event, SourceCreate
from app.services.notifications.scheduler import NotificationScheduler, render_notification_body


def test_scheduler_sends_due_notification_once(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    config_store = AppConfigStore(path)
    config_store.save(
        {
            "sources": [],
            "notifications": {
                "enabled": True,
                "target": "notify_send",
                "webhook": {"url": None, "headers": {}},
                "email": {"to": None},
                "time_format": "%Y-%m-%d %H:%M",
                "body_template": "{title}\n{time}\n{delta}",
            },
        }
    )

    store = SourcesStore(path)
    store.add_source(SourceCreate(type="ics_url", name="A", config={"url": "https://x.test/ics"}))

    now_ms = 1_700_000_000_000
    sent: list[tuple[str, str]] = []

    class DummySender:
        def send(self, title: str, body: str) -> None:
            sent.append((title, body))

    monkeypatch.setattr(
        "app.services.notifications.scheduler.create_sender", lambda settings: DummySender()
    )
    monkeypatch.setattr("app.services.notifications.scheduler.time.time", lambda: now_ms / 1000)

    start = datetime.fromtimestamp((now_ms + 1_000) / 1000, tz=UTC)
    end = start + timedelta(minutes=20)
    event = Event(
        id="evt-1",
        source_id="s1",
        title="Standup",
        start=start,
        end=end,
        alert_minutes_before=[0],
    )

    scheduler = NotificationScheduler(
        sources_store=store,
        config_store=config_store,
        refresh_interval_seconds=60.0,
        aggregate_fn=lambda sources: ([event], [], []),
    )

    scheduler.tick()  # arms alert
    assert sent == []

    now_ms += 2_000
    scheduler.tick()  # due now
    assert len(sent) == 1
    assert sent[0][0] == "Standup"
    assert "Standup" in sent[0][1]
    assert any(token in sent[0][1] for token in ("in", "now", "ago"))

    now_ms += 2_000
    scheduler.tick()  # dedupe prevents duplicate
    assert len(sent) == 1


def test_scheduler_clears_state_when_notifications_disabled(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    config_store = AppConfigStore(path)
    config_store.save(
        {
            "sources": [],
            "notifications": {
                "enabled": False,
                "target": "notify_send",
                "webhook": {"url": None, "headers": {}},
                "email": {"to": None},
            },
        }
    )
    store = SourcesStore(path)

    scheduler = NotificationScheduler(sources_store=store, config_store=config_store)
    scheduler._armed_alerts = [object()]  # type: ignore[list-item]
    scheduler._notified_alerts = {"a"}

    scheduler.tick()

    assert scheduler._armed_alerts == []
    assert scheduler._alert_heap == []
    assert scheduler._notified_alerts == set()


def test_scheduler_does_not_refresh_every_tick(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    config_store = AppConfigStore(path)
    config_store.save(
        {
            "sources": [],
            "notifications": {
                "enabled": True,
                "target": "notify_send",
                "webhook": {"url": None, "headers": {}},
                "email": {"to": None},
            },
        }
    )
    store = SourcesStore(path)
    store.add_source(SourceCreate(type="ics_url", name="A", config={"url": "https://x.test/ics"}))

    now_ms = 1_700_000_000_000
    calls = 0

    class DummySender:
        def send(self, title: str, body: str) -> None:
            pass

    def aggregate(_sources):
        nonlocal calls
        calls += 1
        return ([], [], [])

    monkeypatch.setattr(
        "app.services.notifications.scheduler.create_sender", lambda settings: DummySender()
    )
    monkeypatch.setattr("app.services.notifications.scheduler.time.time", lambda: now_ms / 1000)

    scheduler = NotificationScheduler(
        sources_store=store,
        config_store=config_store,
        refresh_interval_seconds=60.0,
        aggregate_fn=aggregate,
    )

    scheduler.tick()
    assert calls == 1

    now_ms += 1_000
    scheduler.tick()
    now_ms += 1_000
    scheduler.tick()
    assert calls == 1

    now_ms += 60_000
    scheduler.tick()
    assert calls == 2


def test_heap_dispatch_preserves_ordering_and_dedupe(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    config_store = AppConfigStore(path)
    config_store.save(
        {
            "sources": [],
            "notifications": {
                "enabled": True,
                "target": "notify_send",
                "webhook": {"url": None, "headers": {}},
                "email": {"to": None},
                "time_format": "%Y-%m-%d %H:%M",
                "body_template": "{title}",
            },
        }
    )
    store = SourcesStore(path)
    store.add_source(SourceCreate(type="ics_url", name="A", config={"url": "https://x.test/ics"}))

    now_ms = 1_700_000_000_000
    sent: list[str] = []

    class DummySender:
        def send(self, title: str, body: str) -> None:
            sent.append(title)

    monkeypatch.setattr(
        "app.services.notifications.scheduler.create_sender", lambda settings: DummySender()
    )
    monkeypatch.setattr("app.services.notifications.scheduler.time.time", lambda: now_ms / 1000)

    first_start = datetime.fromtimestamp((now_ms + 2_000) / 1000, tz=UTC)
    second_start = datetime.fromtimestamp((now_ms + 4_000) / 1000, tz=UTC)
    events = [
        Event(
            id="evt-1",
            source_id="s1",
            title="First",
            start=first_start,
            end=first_start + timedelta(minutes=10),
            alert_minutes_before=[0],
        ),
        Event(
            id="evt-2",
            source_id="s1",
            title="Second",
            start=second_start,
            end=second_start + timedelta(minutes=10),
            alert_minutes_before=[0],
        ),
    ]

    scheduler = NotificationScheduler(
        sources_store=store,
        config_store=config_store,
        refresh_interval_seconds=60.0,
        aggregate_fn=lambda sources: (events, [], []),
    )

    scheduler.tick()
    now_ms += 2_100
    scheduler.tick()
    assert sent == ["First"]

    now_ms += 2_000
    scheduler.tick()
    assert sent == ["First", "Second"]

    now_ms += 1_000
    scheduler.tick()
    assert sent == ["First", "Second"]


def test_refresh_rebuilds_alerts_when_source_data_changes(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    config_store = AppConfigStore(path)
    config_store.save(
        {
            "sources": [],
            "notifications": {
                "enabled": True,
                "target": "notify_send",
                "webhook": {"url": None, "headers": {}},
                "email": {"to": None},
            },
        }
    )
    store = SourcesStore(path)
    store.add_source(SourceCreate(type="ics_url", name="A", config={"url": "https://x.test/ics"}))

    now_ms = 1_700_000_000_000
    state = {"title": "Before"}

    class DummySender:
        def send(self, title: str, body: str) -> None:
            pass

    def aggregate(_sources):
        start = datetime.fromtimestamp((now_ms + 30_000) / 1000, tz=UTC)
        return (
            [
                Event(
                    id="evt-1",
                    source_id="s1",
                    title=state["title"],
                    start=start,
                    end=start + timedelta(minutes=10),
                    alert_minutes_before=[0],
                )
            ],
            [],
            [],
        )

    monkeypatch.setattr(
        "app.services.notifications.scheduler.create_sender", lambda settings: DummySender()
    )
    monkeypatch.setattr("app.services.notifications.scheduler.time.time", lambda: now_ms / 1000)

    scheduler = NotificationScheduler(
        sources_store=store,
        config_store=config_store,
        refresh_interval_seconds=10.0,
        aggregate_fn=aggregate,
    )

    scheduler.tick()
    assert scheduler._armed_alerts[0].title == "Before"

    state["title"] = "After"
    now_ms += 10_000
    scheduler.tick()
    assert scheduler._armed_alerts[0].title == "After"


def test_stress_many_events_reduces_aggregate_call_frequency(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    config_store = AppConfigStore(path)
    config_store.save(
        {
            "sources": [],
            "notifications": {
                "enabled": True,
                "target": "notify_send",
                "webhook": {"url": None, "headers": {}},
                "email": {"to": None},
            },
        }
    )
    store = SourcesStore(path)
    store.add_source(SourceCreate(type="ics_url", name="A", config={"url": "https://x.test/ics"}))

    now_ms = 1_700_000_000_000
    calls = 0

    class DummySender:
        def send(self, title: str, body: str) -> None:
            pass

    base_start = datetime.fromtimestamp((now_ms + 120_000) / 1000, tz=UTC)
    heavy_events = [
        Event(
            id=f"evt-{idx}",
            source_id="s1",
            title=f"Event {idx}",
            start=base_start + timedelta(minutes=idx),
            end=base_start + timedelta(minutes=idx + 1),
            alert_minutes_before=[0],
        )
        for idx in range(1_000)
    ]

    def aggregate(_sources):
        nonlocal calls
        calls += 1
        return (heavy_events, [], [])

    monkeypatch.setattr(
        "app.services.notifications.scheduler.create_sender", lambda settings: DummySender()
    )
    monkeypatch.setattr("app.services.notifications.scheduler.time.time", lambda: now_ms / 1000)

    scheduler = NotificationScheduler(
        sources_store=store,
        config_store=config_store,
        refresh_interval_seconds=60.0,
        aggregate_fn=aggregate,
    )

    for _ in range(120):
        scheduler.tick()
        now_ms += 1_000

    assert calls <= 3


def test_render_notification_body_supports_multiline_and_delta():
    now_ms = 1_700_000_000_000
    target = datetime.fromtimestamp((now_ms + 5 * 60_000) / 1000, tz=UTC)

    body = render_notification_body(
        title="Deploy",
        kind="event",
        target_dt=target,
        now_ms=now_ms,
        time_format="%Y-%m-%d %H:%M",
        body_template="{title}\n{time}\n{delta}",
    )

    assert body.count("\n") == 2
    assert "Deploy" in body
    assert "in 5m" in body
