import httpx

from app.models.dtos import Source
from app.services.ical_cache import parse_events_cached
from app.services.ical_recurrence import parse_iso_window
from app.services.sources.base import FetchResult, SourceDriver


class IcsUrlDriver(SourceDriver):
    """Read-only ICS URL subscription."""

    def fetch(
        self,
        source: Source,
        start: str | None = None,
        end: str | None = None,
    ) -> FetchResult:
        url = source.config.get("url")
        if not url:
            return FetchResult([], [], errors=["Missing url in config"])
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                text = resp.text
        except Exception as e:
            return FetchResult([], [], errors=[str(e)])
        window_start, window_end = parse_iso_window(start, end)
        etag = resp.headers.get("etag") if hasattr(resp, "headers") else None
        last_modified = resp.headers.get("last-modified") if hasattr(resp, "headers") else None
        fingerprint = f"etag:{etag}|lm:{last_modified}" if (etag or last_modified) else None
        events = parse_events_cached(
            text,
            source.id,
            window_start=window_start,
            window_end=window_end,
            fingerprint=fingerprint,
        )
        return FetchResult(events=events, todos=[])
