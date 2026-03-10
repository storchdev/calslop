import httpx

from app.models.dtos import Source
from app.services.ical_recurrence import parse_iso_window
from app.services.ical_utils import parse_events_from_ical
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
        events = parse_events_from_ical(text, source.id, window_start=window_start, window_end=window_end)
        return FetchResult(events=events, todos=[])
