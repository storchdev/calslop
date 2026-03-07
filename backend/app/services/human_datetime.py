from __future__ import annotations

from contextlib import suppress
from datetime import date, datetime, time, timezone, tzinfo
from zoneinfo import ZoneInfo

import parsedatetime


_calendar = parsedatetime.Calendar(version=parsedatetime.VERSION_CONTEXT_STYLE)


def _tz_from_name(timezone_name: str | None) -> tzinfo:
    if timezone_name:
        return ZoneInfo(timezone_name)
    local_tz = datetime.now().astimezone().tzinfo
    if local_tz is None:
        raise ValueError("Could not determine local timezone")
    return local_tz


def _parse_status_has_datetime(status: object) -> bool:
    has_date_or_time = getattr(status, "hasDateOrTime", None)
    if isinstance(has_date_or_time, bool):
        return has_date_or_time
    if isinstance(status, int):
        return status != 0
    return bool(status)


def _parse_status_has_date(status: object) -> bool:
    has_date = getattr(status, "hasDate", None)
    if isinstance(has_date, bool):
        return has_date
    return False


def _source_time_from_context(context_local: str | None, tz: tzinfo) -> datetime:
    if context_local:
        with suppress(ValueError):
            parsed = datetime.fromisoformat(context_local)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=tz)
            return parsed.astimezone(tz)
    return datetime.now(tz)


def parse_human_datetime(
    value: str,
    timezone_name: str | None = None,
    context_local: str | None = None,
) -> tuple[datetime, bool]:
    text = value.strip()
    if not text:
        raise ValueError("Time description not recognized")

    tz = _tz_from_name(timezone_name)
    source_time = _source_time_from_context(context_local, tz)

    with suppress(ValueError):
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=tz), True
        return dt.astimezone(tz), True

    with suppress(ValueError):
        d = date.fromisoformat(text)
        return datetime.combine(d, time.min, tzinfo=tz), True

    dt, status = _calendar.parseDT(text, sourceTime=source_time, tzinfo=tz)
    if not _parse_status_has_datetime(status):
        raise ValueError(f"Time description not recognized: {value}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz), _parse_status_has_date(status)


def parse_human_datetime_to_utc_iso(
    value: str,
    timezone_name: str | None = None,
    context_local: str | None = None,
) -> tuple[str, bool]:
    parsed, has_date = parse_human_datetime(value, timezone_name, context_local)
    return parsed.astimezone(timezone.utc).isoformat(), has_date
