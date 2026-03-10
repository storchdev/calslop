"""In-memory + JSON file persistence for calendar sources. Can be replaced with SQLite later."""

import json
from pathlib import Path
import uuid

from app.db.app_config_store import AppConfigStore, default_config_path
from app.models.dtos import Source, SourceCreate, SourceUpdate


DEFAULT_SOURCE_COLORS = [
    "#2563eb",
    "#059669",
    "#ea580c",
    "#dc2626",
    "#7c3aed",
    "#0d9488",
    "#b45309",
    "#db2777",
]


class SourcesStore:
    def __init__(self, path: Path | None = None):
        self._path = path or default_config_path()
        self._config_store = AppConfigStore(self._path)
        self._sources: dict[str, Source] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = self._config_store.load()
            for raw in data.get("sources", []):
                s = Source.model_validate(raw)
                self._sources[s.id] = s
        except (json.JSONDecodeError, OSError, Exception):
            self._sources = {}

    def _save(self) -> None:
        data = self._config_store.load()
        data["sources"] = [s.model_dump(mode="json") for s in self._sources.values()]
        self._config_store.save(data)

    def list_sources(self) -> list[Source]:
        return list(self._sources.values())

    def get_source(self, source_id: str) -> Source | None:
        return self._sources.get(source_id)

    def add_source(self, data: SourceCreate) -> Source:
        sid = str(uuid.uuid4())
        default_color = DEFAULT_SOURCE_COLORS[len(self._sources) % len(DEFAULT_SOURCE_COLORS)]
        source = Source(
            id=sid,
            type=data.type,
            name=data.name,
            enabled=data.enabled,
            color=data.color or default_color,
            config=data.config,
        )
        self._sources[sid] = source
        self._save()
        return source

    def update_source(self, source_id: str, data: SourceUpdate) -> Source | None:
        s = self._sources.get(source_id)
        if not s:
            return None
        d = s.model_dump()
        if data.name is not None:
            d["name"] = data.name
        if data.enabled is not None:
            d["enabled"] = data.enabled
        if data.color is not None:
            d["color"] = data.color
        if data.config is not None:
            d["config"] = data.config
        s = Source(**d)
        self._sources[source_id] = s
        self._save()
        return s

    def delete_source(self, source_id: str) -> bool:
        if source_id in self._sources:
            del self._sources[source_id]
            self._save()
            return True
        return False
