from datetime import datetime

from app.services import ical_cache
from app.services.ical_utils import parse_todos_from_ical


def _todo_rrule_ics() -> str:
    return "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Test//EN",
            "BEGIN:VTODO",
            "UID:todo-series-1@example.com",
            "DUE:20200101T090000Z",
            "SUMMARY:Daily task",
            "RRULE:FREQ=DAILY",
            "END:VTODO",
            "END:VCALENDAR",
        ]
    )


def test_parse_todos_window_filters_recurrence_to_requested_window():
    todos = parse_todos_from_ical(
        _todo_rrule_ics(),
        "src-todo",
        window_start=datetime(2026, 1, 10, 0, 0),
        window_end=datetime(2026, 1, 10, 23, 59),
    )
    assert len(todos) == 1
    assert todos[0].due is not None
    assert todos[0].due.strftime("%Y-%m-%d") == "2026-01-10"


def test_parse_todos_cached_reuses_parse_for_identical_fingerprint(monkeypatch):
    calls = {"count": 0}

    def fake_parse(*args, **kwargs):
        calls["count"] += 1
        return []

    monkeypatch.setattr(ical_cache, "parse_todos_from_ical", fake_parse)
    text = _todo_rrule_ics()
    fp = "etag:test-1"

    first = ical_cache.parse_todos_cached(
        text,
        "src-cache",
        window_start=None,
        window_end=None,
        fingerprint=fp,
    )
    second = ical_cache.parse_todos_cached(
        text,
        "src-cache",
        window_start=None,
        window_end=None,
        fingerprint=fp,
    )

    assert first == []
    assert second == []
    assert calls["count"] == 1


def test_parse_todos_cached_invalidates_source(monkeypatch):
    calls = {"count": 0}

    def fake_parse(*args, **kwargs):
        calls["count"] += 1
        return []

    monkeypatch.setattr(ical_cache, "parse_todos_from_ical", fake_parse)
    text = _todo_rrule_ics()
    fp = "etag:test-2"

    ical_cache.parse_todos_cached(
        text,
        "src-invalidate",
        window_start=None,
        window_end=None,
        fingerprint=fp,
    )
    ical_cache.invalidate_source_cache("src-invalidate")
    ical_cache.parse_todos_cached(
        text,
        "src-invalidate",
        window_start=None,
        window_end=None,
        fingerprint=fp,
    )

    assert calls["count"] == 2
