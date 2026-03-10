from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_config_path() -> Path:
    import os

    if os.environ.get("CALSLOP_DATA_DIR"):
        return Path(os.environ["CALSLOP_DATA_DIR"]) / "sources.json"
    return Path.home() / ".config" / "calslop" / "sources.json"


class AppConfigStore:
    def __init__(self, path: Path | None = None):
        self._path = path or default_config_path()

    def load(self) -> dict[str, Any]:
        try:
            if not self._path.exists():
                return {}
            data = json.loads(self._path.read_text())
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError, ValueError):
            pass
        return {}

    def save(self, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(data, indent=2))
        except OSError:
            pass
