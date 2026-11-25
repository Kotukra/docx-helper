"""Theme palette helpers kept independent from the GUI for safe validation."""
from __future__ import annotations

import re

COLOR_KEYS = ("background", "surface", "control", "text", "accent", "border")
DEFAULT_COLORS = {
    "background": "#121212",
    "surface": "#1e1e1e",
    "control": "#2a2a2a",
    "text": "#e0e0e0",
    "accent": "#7c4dff",
    "border": "#444444",
}
BUILTIN_PALETTES = {
    "dark": {"name": "Тёмная", "colors": DEFAULT_COLORS},
    "light": {"name": "Светлая", "colors": {
        "background": "#f4f5f7", "surface": "#ffffff", "control": "#eef0f3",
        "text": "#20242b", "accent": "#5b4bdb", "border": "#c9ced6",
    }},
    "ocean": {"name": "Океан", "colors": {
        "background": "#0e1b24", "surface": "#142936", "control": "#1d3948",
        "text": "#e2f1f6", "accent": "#29b6a6", "border": "#315465",
    }},
}


def normalize_colors(colors=None, legacy_accent=None):
    result = dict(DEFAULT_COLORS)
    if isinstance(colors, dict):
        result.update({key: value for key, value in colors.items() if key in COLOR_KEYS})
    elif legacy_accent:
        result["accent"] = legacy_accent
    for key, value in result.items():
        if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError(f"Цвет {key} должен быть в формате #RRGGBB")
        result[key] = value.lower()
    return result


def normalize_palettes(palettes):
    if palettes is None:
        return []
    if not isinstance(palettes, list):
        raise ValueError("Список пользовательских палитр должен быть списком")
    result = []
    names = set()
    for item in palettes:
        if not isinstance(item, dict) or not str(item.get("name", "")).strip():
            continue
        name = str(item["name"]).strip()
        if name.casefold() in names:
            continue
        names.add(name.casefold())
        result.append({"name": name, "colors": normalize_colors(item.get("colors"))})
    return result
