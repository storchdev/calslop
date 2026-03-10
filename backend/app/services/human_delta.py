from __future__ import annotations

import re

_TOKEN_RE = re.compile(
    r"(?P<count>\d+)\s*(?P<unit>s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)",
    re.IGNORECASE,
)

_UNIT_TO_SECONDS = {
    "s": 1,
    "sec": 1,
    "secs": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "mins": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
}


def _canonical_label(seconds: int) -> str:
    sign = "+" if seconds >= 0 else "-"
    remaining = abs(seconds)
    if remaining == 0:
        return "+0s"

    parts: list[str] = []
    days, remaining = divmod(remaining, 86400)
    hours, remaining = divmod(remaining, 3600)
    minutes, remaining = divmod(remaining, 60)

    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if remaining:
        parts.append(f"{remaining}s")

    return f"{sign}{' '.join(parts)}"


def parse_human_delta(text: str) -> tuple[int, str]:
    raw = text.strip()
    if not raw:
        raise ValueError("Delta text is required")

    sign = 1
    if raw[0] in {"+", "-"}:
        sign = -1 if raw[0] == "-" else 1
        raw = raw[1:].strip()

    if not raw:
        raise ValueError("Duration is required after sign")

    total_seconds = 0
    position = 0
    matches = list(_TOKEN_RE.finditer(raw))
    if not matches:
        raise ValueError("Could not parse duration; use forms like +2h 30m or -1 day")

    for match in matches:
        between = raw[position : match.start()]
        if between.strip():
            raise ValueError(f"Unrecognized duration segment: {between.strip()}")

        count = int(match.group("count"))
        unit = match.group("unit").lower()
        total_seconds += count * _UNIT_TO_SECONDS[unit]
        position = match.end()

    if raw[position:].strip():
        raise ValueError(f"Unrecognized duration segment: {raw[position:].strip()}")

    signed_seconds = sign * total_seconds
    return signed_seconds, _canonical_label(signed_seconds)
