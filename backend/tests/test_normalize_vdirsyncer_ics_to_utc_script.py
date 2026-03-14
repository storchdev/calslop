from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "normalize_vdirsyncer_ics_to_utc.py"
_SPEC = spec_from_file_location("normalize_vdirsyncer_ics_to_utc", SCRIPT_PATH)
assert _SPEC and _SPEC.loader
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
normalize_calendar_for_ios_todos = _MODULE.normalize_calendar_for_ios_todos
normalize_calendar_for_ios_todos_in_tz = _MODULE.normalize_calendar_for_ios_todos_in_tz


def test_script_keeps_recurring_event_tzid_to_avoid_dst_drift():
    ics_text = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Test//EN",
            "BEGIN:VEVENT",
            "UID:dst-series@example.com",
            "DTSTART;TZID=America/New_York:20260307T090000",
            "DTEND;TZID=America/New_York:20260307T100000",
            "RRULE:FREQ=DAILY;COUNT=4",
            "SUMMARY:DST Series",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    ).encode("utf-8")

    rewritten, changed = normalize_calendar_for_ios_todos(ics_text)
    out = rewritten.decode("utf-8")

    assert changed == 0
    assert "DTSTART;TZID=America/New_York:20260307T090000" in out
    assert "DTSTART:20260307T140000Z" not in out


def test_script_converts_recurring_utc_event_to_target_tzid_for_dst_stability():
    ics_text = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Test//EN",
            "BEGIN:VEVENT",
            "UID:QG9ZJMZFU9UOEECEU1QT1K3EU82WVZPA0GXV",
            "DTSTART:20260123T172000Z",
            "DTEND:20260123T181000Z",
            "EXDATE:20260227T172000Z",
            "RRULE:FREQ=WEEKLY;UNTIL=20260306T235959Z",
            "SUMMARY:diffeq quiz",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    ).encode("utf-8")

    rewritten, changed = normalize_calendar_for_ios_todos_in_tz(
        ics_text, _MODULE.ZoneInfo("America/New_York")
    )
    out = rewritten.decode("utf-8")

    assert changed >= 2
    assert "DTSTART;TZID=America/New_York:20260123T122000" in out
    assert "DTEND;TZID=America/New_York:20260123T131000" in out
    assert "EXDATE;TZID=America/New_York:20260227T122000" in out
    assert "DTSTART:20260123T172000Z" not in out


def test_script_rewrites_todo_due_and_recurrence_values_to_target_tzid():
    ics_text = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Test//EN",
            "BEGIN:VTODO",
            "UID:todo-series@example.com",
            "SUMMARY:Pay bill",
            "DTSTART;TZID=America/New_York:20260307T090000",
            "DUE;TZID=America/New_York:20260307T093000",
            "RRULE:FREQ=DAILY;COUNT=2",
            "RECURRENCE-ID;TZID=America/New_York:20260308T090000",
            "EXDATE;TZID=America/New_York:20260309T090000",
            "RDATE;TZID=America/New_York:20260310T090000",
            "END:VTODO",
            "END:VCALENDAR",
        ]
    ).encode("utf-8")

    rewritten, changed = normalize_calendar_for_ios_todos_in_tz(
        ics_text, _MODULE.ZoneInfo("America/New_York")
    )
    out = rewritten.decode("utf-8")

    assert changed == 0
    assert "DUE;TZID=America/New_York:20260307T093000" in out
    assert "DTSTART;TZID=America/New_York:20260307T090000" in out
    assert "RECURRENCE-ID;TZID=America/New_York:20260308T090000" in out
    assert "EXDATE;TZID=America/New_York:20260309T090000" in out
    assert "RDATE;TZID=America/New_York:20260310T090000" in out


def test_script_converts_utc_vtodo_due_to_target_local_wall_time():
    ics_text = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Test//EN",
            "BEGIN:VTODO",
            "UID:todo-utc@example.com",
            "SUMMARY:UTC todo",
            "DUE:20260314T020000Z",
            "END:VTODO",
            "END:VCALENDAR",
        ]
    ).encode("utf-8")

    rewritten, changed = normalize_calendar_for_ios_todos_in_tz(
        ics_text, _MODULE.ZoneInfo("America/New_York")
    )
    out = rewritten.decode("utf-8")

    assert changed >= 1
    assert "DUE;TZID=America/New_York:20260313T220000" in out
    assert "DUE:20260314T020000Z" not in out
