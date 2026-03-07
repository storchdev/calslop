from __future__ import annotations

import re


_RE_BASIC = re.compile(
    r"^\s*(?P<num>\d+)\s*(?P<unit>m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\s*(before|early|prior)?\s*$",
    re.IGNORECASE,
)


def _parse_one_alert_token(token: str) -> int:
    t = token.strip().lower()
    if not t:
        raise ValueError("Empty alert value")

    if t in {"at time", "at due time", "at start", "at event time", "when due", "when it starts", "0"}:
        return 0

    m = _RE_BASIC.match(t)
    if not m:
        raise ValueError(f"Could not parse alert value: {token}")

    num = int(m.group("num"))
    unit = m.group("unit").lower()
    if unit.startswith("m"):
        return num
    if unit.startswith("h"):
        return num * 60
    if unit.startswith("d"):
        return num * 1440
    raise ValueError(f"Unsupported alert unit: {unit}")


def _format_minutes_label(minutes: int) -> str:
    if minutes == 0:
        return "at time"
    if minutes % 1440 == 0:
        days = minutes // 1440
        return f"{days}d before"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours}h before"
    return f"{minutes}m before"


def parse_human_alerts(text: str) -> tuple[list[int], str]:
    raw = text.strip()
    if not raw:
        raise ValueError("Alert text is required")

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError("Provide at least one alert value")

    values = sorted({_parse_one_alert_token(p) for p in parts})
    label = ", ".join(_format_minutes_label(v) for v in values)
    return values, label
