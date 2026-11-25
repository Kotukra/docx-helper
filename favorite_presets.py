"""Persistence for named user favorites of document-generation settings."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path


def _default_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home())) / "GostDocumentGenerator"
    return base / "favorite_presets.json"


class FavoritePresetManager:
    EXCLUDED = {
        "accent_color", "ui_colors", "ui_palettes", "ui_palette_name",
        "advanced_settings", "app_mode", "debug_mode", "output_folder",
        "saved_folders", "recent_documents", "recent_projects",
        "app_version", "update_manifest_url",
    }

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else _default_path()

    def _read(self) -> dict:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def names(self) -> list[str]:
        return sorted(self._read(), key=str.casefold)

    def get(self, name: str) -> dict | None:
        value = self._read().get(name)
        return deepcopy(value) if isinstance(value, dict) else None

    def save(self, name: str, settings: dict) -> None:
        name = str(name or "").strip()
        if not name or len(name) > 60:
            raise ValueError("Название избранного должно содержать от 1 до 60 символов")
        values = {key: deepcopy(value) for key, value in settings.items()
                  if key not in self.EXCLUDED and not key.startswith("ui_")}
        data = self._read()
        data[name] = values
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def delete(self, name: str) -> bool:
        data = self._read()
        if name not in data:
            return False
        del data[name]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
