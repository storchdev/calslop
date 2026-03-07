from __future__ import annotations

import re


_UNIT_ALIASES = {
    "minute": "MINUTELY",
    "minutes": "MINUTELY",
    "min": "MINUTELY",
    "mins": "MINUTELY",
    "hour": "HOURLY",
    "hours": "HOURLY",
    "hr": "HOURLY",
    "hrs": "HOURLY",
    "day": "DAILY",
    "days": "DAILY",
    "daily": "DAILY",
    "week": "WEEKLY",
    "weeks": "WEEKLY",
    "weekly": "WEEKLY",
    "month": "MONTHLY",
    "months": "MONTHLY",
    "monthly": "MONTHLY",
    "year": "YEARLY",
    "years": "YEARLY",
    "yearly": "YEARLY",
    "annually": "YEARLY",
    "annual": "YEARLY",
}

_DISPLAY_SINGULAR = {
    "MINUTELY": "minute",
    "HOURLY": "hour",
    "DAILY": "day",
    "WEEKLY": "week",
    "MONTHLY": "month",
    "YEARLY": "year",
}


def _pluralize(word: str, n: int) -> str:
    return word if n == 1 else f"{word}s"


def parse_human_recurrence(value: str) -> tuple[str, str]:
    text = re.sub(r"\s+", " ", value.strip().lower())
    if not text:
        raise ValueError("Recurrence description not recognized")

    text = re.sub(r"^every\s+", "", text)

    direct = _UNIT_ALIASES.get(text)
    if direct:
        singular = _DISPLAY_SINGULAR[direct]
        return f"FREQ={direct}", f"Every {singular}"

    match = re.fullmatch(r"(?:(\d+)\s+)?([a-z]+)", text)
    if not match:
        raise ValueError(f"Recurrence description not recognized: {value}")

    n_raw, unit_raw = match.groups()
    interval = int(n_raw) if n_raw else 1
    if interval <= 0:
        raise ValueError("Recurrence interval must be greater than 0")

    freq = _UNIT_ALIASES.get(unit_raw)
    if not freq:
        raise ValueError(f"Recurrence description not recognized: {value}")

    singular = _DISPLAY_SINGULAR[freq]
    label = f"Every {interval} {_pluralize(singular, interval)}"
    if interval == 1:
        return f"FREQ={freq}", label
    return f"FREQ={freq};INTERVAL={interval}", label
