from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from hashlib import sha1
from threading import RLock

from app.models.dtos import Event, Todo
from app.services.ical_utils import parse_events_from_ical, parse_todos_from_ical

_MAX_CACHE_ENTRIES = 512


def _window_key(dt: datetime | None) -> str:
    return dt.isoformat() if dt is not None else "-"


def _content_fingerprint(ical_text: str | bytes, fingerprint: str | None) -> str:
    if fingerprint:
        return fingerprint
    payload = ical_text.encode("utf-8") if isinstance(ical_text, str) else ical_text
    return f"sha1:{sha1(payload).hexdigest()}"


class _ParseCache:
    def __init__(self):
        self._lock = RLock()
        self._entries: OrderedDict[tuple[str, ...], list[Event] | list[Todo]] = OrderedDict()

    def get(self, key: tuple[str, ...]) -> list[Event] | list[Todo] | None:
        with self._lock:
            val = self._entries.get(key)
            if val is None:
                return None
            self._entries.move_to_end(key)
            return list(val)

    def set(self, key: tuple[str, ...], value: list[Event] | list[Todo]) -> None:
        with self._lock:
            self._entries[key] = list(value)
            self._entries.move_to_end(key)
            while len(self._entries) > _MAX_CACHE_ENTRIES:
                self._entries.popitem(last=False)

    def invalidate_source(self, source_id: str) -> None:
        with self._lock:
            keys_to_drop = [
                key
                for key in self._entries
                if key[1] == source_id or key[1].startswith(f"{source_id}::")
            ]
            for key in keys_to_drop:
                self._entries.pop(key, None)


_CACHE = _ParseCache()


def parse_events_cached(
    ical_text: str | bytes,
    source_id: str,
    *,
    window_start: datetime | None,
    window_end: datetime | None,
    fingerprint: str | None = None,
) -> list[Event]:
    fp = _content_fingerprint(ical_text, fingerprint)
    key = ("events", source_id, fp, _window_key(window_start), _window_key(window_end))
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    parsed = parse_events_from_ical(
        ical_text,
        source_id,
        window_start=window_start,
        window_end=window_end,
    )
    _CACHE.set(key, parsed)
    return list(parsed)


def parse_todos_cached(
    ical_text: str | bytes,
    source_id: str,
    *,
    window_start: datetime | None,
    window_end: datetime | None,
    fingerprint: str | None = None,
) -> list[Todo]:
    fp = _content_fingerprint(ical_text, fingerprint)
    key = ("todos", source_id, fp, _window_key(window_start), _window_key(window_end))
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    parsed = parse_todos_from_ical(
        ical_text,
        source_id,
        window_start=window_start,
        window_end=window_end,
    )
    _CACHE.set(key, parsed)
    return list(parsed)


def invalidate_source_cache(source_id: str) -> None:
    _CACHE.invalidate_source(source_id)
