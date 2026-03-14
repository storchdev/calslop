from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.dtos import Event, Todo
import app.services.ical_utils as ical_utils
from app.services.ical_utils import (
    build_exception_vtodo,
    event_to_ical,
    merge_instance_todo_into_ical,
    todo_to_ical,
)


def test_event_to_ical_serializes_datetime_values_as_utc():
    event = Event(
        id="src-1::evt-1@example.com",
        source_id="src-1",
        title="Morning Sync",
        start=datetime(2026, 3, 7, 9, 0, tzinfo=ZoneInfo("America/New_York")),
        end=datetime(2026, 3, 7, 10, 0, tzinfo=ZoneInfo("America/New_York")),
        all_day=False,
    )

    ics_text = event_to_ical(event).decode("utf-8")

    assert "DTSTART:20260307T140000Z" in ics_text
    assert "DTEND:20260307T150000Z" in ics_text
    assert "TZID=" not in ics_text


def test_todo_to_ical_serializes_due_with_local_tzid_for_ios(monkeypatch):
    monkeypatch.setattr(ical_utils, "_local_timezone", lambda: ZoneInfo("America/New_York"))
    todo = Todo(
        id="src-1::todo-1@example.com",
        source_id="src-1",
        summary="Submit report",
        due=datetime(2026, 3, 7, 9, 30, tzinfo=ZoneInfo("America/New_York")),
        categories=["Work", "Urgent"],
    )

    ics_text = todo_to_ical(todo).decode("utf-8")

    assert "DTSTART;TZID=America/New_York:20260307T093000" in ics_text
    assert "DUE;TZID=America/New_York:20260307T093000" in ics_text
    assert "CATEGORIES:Work,Urgent" in ics_text


def test_instance_todo_serializers_keep_due_in_local_tzid(monkeypatch):
    monkeypatch.setattr(ical_utils, "_local_timezone", lambda: ZoneInfo("America/New_York"))
    base_ical = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Test//EN",
            "BEGIN:VTODO",
            "UID:todo-series@example.com",
            "SUMMARY:Series",
            "RRULE:FREQ=DAILY;COUNT=3",
            "END:VTODO",
            "END:VCALENDAR",
        ]
    ).encode("utf-8")
    due_local = datetime(2026, 3, 8, 11, 15, tzinfo=ZoneInfo("America/New_York"))
    todo = Todo(
        id="src-1::todo-series@example.com::20260308T130000Z",
        source_id="src-1",
        summary="Series",
        due=due_local,
        categories=["Work", "Follow Up"],
    )

    merged_text = merge_instance_todo_into_ical(base_ical, todo, "20260308T130000Z").decode("utf-8")
    exception_text = build_exception_vtodo(
        uid="todo-series@example.com",
        recurrence_id_str="20260308T130000Z",
        summary="Series",
        due=due_local,
        description=None,
        priority=None,
        categories=["Work", "Follow Up"],
    ).decode("utf-8")

    assert "RECURRENCE-ID;TZID=America/New_York:20260308T090000" in merged_text
    assert "DUE;TZID=America/New_York:20260308T111500" in merged_text
    assert "DTSTART;TZID=America/New_York:20260308T111500" in merged_text
    assert "RECURRENCE-ID;TZID=America/New_York:20260308T090000" in exception_text
    assert "DUE;TZID=America/New_York:20260308T111500" in exception_text
    assert "DTSTART;TZID=America/New_York:20260308T111500" in exception_text
    assert "CATEGORIES:Work,Follow Up" in merged_text
    assert "CATEGORIES:Work,Follow Up" in exception_text
