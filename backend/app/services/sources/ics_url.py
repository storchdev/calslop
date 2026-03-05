import httpx

from app.models.dtos import Event, Source
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
        events = parse_events_from_ical(text, source.id)
        # Optional: filter by start/end if provided
        if start and end:
            from datetime import datetime
            try:
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00")).replace(tzinfo=None)
                end_dt = datetime.fromisoformat(end.replace("Z", "+00:00")).replace(tzinfo=None)
                events = [e for e in events if e.end >= start_dt and e.start <= end_dt]
            except (ValueError, TypeError):
                pass
        return FetchResult(events=events, todos=[])
