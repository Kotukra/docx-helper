# settings_manager.py
import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Optional
from constants import DEFAULT_SETTINGS_PATH, DOCUMENT_SETTINGS_PATH

class SettingsManager:
    def __init__(self):
        self._settings: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = {}
        self._load_defaults()

    def _load_defaults(self):
        if os.path.exists(DEFAULT_SETTINGS_PATH):
            try:
                with open(DEFAULT_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    self._defaults = json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки default_settings.json: {e}")
                self._defaults = {}
        else:
            self._defaults = {}
        self._settings = deepcopy(self._defaults)
        if "accent_color" not in self._settings:
            self._settings["accent_color"] = "#7c4dff"
        # Добавляем отладочный режим по умолчанию (выключен)
        if "debug_mode" not in self._settings:
            self._settings["debug_mode"] = False

    def get(self, key: str, default=None):
        return self._settings.get(key, default)

    def set(self, key: str, value: Any):
        self._settings[key] = value

    def update(self, data: Dict[str, Any]):
        self._settings.update(data)

    def get_all(self) -> Dict[str, Any]:
        return self._settings.copy()

    def get_default(self, key: str, default=None):
        return self._defaults.get(key, default)

    def load_from_file(self, path: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Preserve accent colors saved by versions predating full UI palettes.
            if isinstance(data, dict) and "ui_colors" not in data and "accent_color" in data:
                colors = deepcopy(self._settings.get("ui_colors", {}))
                colors["accent"] = data["accent_color"]
                data["ui_colors"] = colors
                if data["accent_color"] != self._settings.get("accent_color", "#7c4dff"):
                    data["ui_palette_name"] = "Пользовательская"
            self.update(data)
            return True
        except Exception as e:
            print(f"Ошибка загрузки {path}: {e}")
            return False

    def save_to_file(self, path: str, data: Optional[Dict] = None) -> bool:
        try:
            if data is None:
                data = self._settings
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"Ошибка сохранения {path}: {e}")
            return False

    def reset_to_defaults(self):
        self._settings = deepcopy(self._defaults)
        if "accent_color" not in self._settings:
            self._settings["accent_color"] = "#7c4dff"
        if "debug_mode" not in self._settings:
            self._settings["debug_mode"] = False

    def get_filename_template(self) -> str:
        parts = []
        if self.get("filename_use_keywords", False):
            parts.append("{keywords}")
        if self.get("filename_use_date", False):
            parts.append("{date}")
        if self.get("filename_use_time", False):
            parts.append("{time}")
        if self.get("filename_use_part", False):
            parts.append("{part}")
        sep = self.get("filename_separator", "_")
        return sep.join(parts) if parts else "{keywords}"
