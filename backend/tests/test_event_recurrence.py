import json
from datetime import datetime

from app.main import app
from app.models.dtos import Source
from app.services.ical_utils import parse_events_from_ical
from app.services.sources.ics_url import IcsUrlDriver
from app.services.sources.local_folder import LocalFolderDriver


def _recurring_ics(*, with_exception: bool = False, with_exdate: bool = False) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Test//EN",
        "BEGIN:VEVENT",
        "UID:series-1@example.com",
        "DTSTART:20260101T090000Z",
        "DTEND:20260101T100000Z",
        "SUMMARY:Daily Standup",
        "RRULE:FREQ=DAILY;COUNT=5",
    ]
    if with_exdate:
        lines.append("EXDATE:20260103T090000Z")
    lines.extend(["END:VEVENT"])
    if with_exception:
        lines.extend(
            [
                "BEGIN:VEVENT",
                "UID:series-1@example.com",
                "RECURRENCE-ID:20260102T090000Z",
                "DTSTART:20260102T110000Z",
                "DTEND:20260102T120000Z",
                "SUMMARY:Rescheduled Standup",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\n".join(lines)


def test_parse_recurring_events_expand_when_master_outside_window():
    events = parse_events_from_ical(
        _recurring_ics(),
        "src-1",
        window_start=datetime(2026, 1, 4, 0, 0),
        window_end=datetime(2026, 1, 5, 23, 59),
    )
    assert [e.start.strftime("%Y-%m-%d") for e in events] == ["2026-01-04", "2026-01-05"]
    assert all(e.recurrence == "FREQ=DAILY;COUNT=5" for e in events)
    assert all(e.id.startswith("src-1::series-1@example.com::") for e in events)


def test_parse_recurrence_id_exception_overrides_instance():
    events = parse_events_from_ical(
        _recurring_ics(with_exception=True),
        "src-2",
        window_start=datetime(2026, 1, 2, 0, 0),
        window_end=datetime(2026, 1, 2, 23, 59),
    )
    assert len(events) == 1
    assert events[0].title == "Rescheduled Standup"
    assert events[0].start.hour == 11
    assert events[0].id == "src-2::series-1@example.com::20260102T090000Z"


def test_parse_exdate_suppresses_instance():
    events = parse_events_from_ical(
        _recurring_ics(with_exdate=True),
        "src-3",
        window_start=datetime(2026, 1, 1, 0, 0),
        window_end=datetime(2026, 1, 5, 23, 59),
    )
    ids = [e.id for e in events]
    assert "src-3::series-1@example.com::20260103T090000Z" not in ids
    assert len(ids) == len(set(ids))


def test_parse_non_recurring_event_unchanged():
    ics_text = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Test//EN",
            "BEGIN:VEVENT",
            "UID:single-1@example.com",
            "DTSTART:20260110T090000Z",
            "DTEND:20260110T100000Z",
            "SUMMARY:One-off",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    )
    events = parse_events_from_ical(ics_text, "src-4")
    assert len(events) == 1
    assert events[0].id == "src-4::single-1@example.com"
    assert events[0].recurrence is None


def test_ics_url_driver_fetches_recurrences_in_window(monkeypatch):
    class FakeResponse:
        text = _recurring_ics()

        @staticmethod
        def raise_for_status():
            return None

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            return FakeResponse()

    monkeypatch.setattr("app.services.sources.ics_url.httpx.Client", FakeClient)
    driver = IcsUrlDriver()
    source = Source(id="source-url", type="ics_url", name="ics", config={"url": "https://example.test/cal.ics"})
    result = driver.fetch(source, start="2026-01-04T00:00:00Z", end="2026-01-05T23:59:00Z")
    assert [e.start.strftime("%Y-%m-%d") for e in result.events] == ["2026-01-04", "2026-01-05"]


def test_local_folder_driver_fetches_recurrences_in_window(tmp_path):
    ics_path = tmp_path / "series.ics"
    ics_path.write_text(_recurring_ics(), encoding="utf-8")
    driver = LocalFolderDriver()
    source = Source(id="source-local", type="local_folder", name="local", config={"path": str(tmp_path)})
    result = driver.fetch(source, start="2026-01-04T00:00:00Z", end="2026-01-05T23:59:00Z")
    assert [e.start.strftime("%Y-%m-%d") for e in result.events] == ["2026-01-04", "2026-01-05"]


def test_events_api_returns_recurring_subscribed_instances(tmp_path, monkeypatch):
    folder = tmp_path / "ics"
    folder.mkdir()
    (folder / "series.ics").write_text(_recurring_ics(), encoding="utf-8")

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sources_json = data_dir / "sources.json"
    sources_json.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "id": "src-local",
                        "type": "local_folder",
                        "name": "Local",
                        "enabled": True,
                        "color": "#2563eb",
                        "config": {"path": str(folder)},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CALSLOP_DATA_DIR", str(data_dir))

    client = app.test_client()
    resp = client.get("/api/events?start=2026-01-04T00:00:00Z&end=2026-01-05T23:59:00Z")
    assert resp.status_code == 200
    payload = resp.get_json()
    payload = sorted(payload, key=lambda item: item["start"])
    assert len(payload) == 2
    assert payload[0]["id"].startswith("src-local::series::series-1@example.com::")
