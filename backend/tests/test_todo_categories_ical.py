from datetime import datetime, timezone

from app.models.dtos import Todo
from app.services.ical_utils import parse_todos_from_ical, todo_to_ical


def test_parse_vtodo_categories_single_and_multiple_values():
    ics_text = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Test//EN",
            "BEGIN:VTODO",
            "UID:todo-categories@example.com",
            "SUMMARY:Categorized",
            "DUE:20260307T120000Z",
            "CATEGORIES:Work,Errands",
            "END:VTODO",
            "END:VCALENDAR",
        ]
    )

    todos = parse_todos_from_ical(ics_text, "src-1")

    assert len(todos) == 1
    assert todos[0].categories == ["Work", "Errands"]


def test_todo_categories_survive_serialize_parse_round_trip():
    todo = Todo(
        id="src-1::todo-roundtrip@example.com",
        source_id="src-1",
        summary="Round trip",
        due=datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc),
        categories=["Home", "Weekend"],
    )

    parsed = parse_todos_from_ical(todo_to_ical(todo), "src-1")

    assert len(parsed) == 1
    assert parsed[0].categories == ["Home", "Weekend"]


def test_vtodo_without_categories_keeps_categories_none():
    ics_text = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Test//EN",
            "BEGIN:VTODO",
            "UID:todo-no-categories@example.com",
            "SUMMARY:No categories",
            "DUE:20260307T120000Z",
            "END:VTODO",
            "END:VCALENDAR",
        ]
    )

    todos = parse_todos_from_ical(ics_text, "src-1")

    assert len(todos) == 1
    assert todos[0].categories is None
