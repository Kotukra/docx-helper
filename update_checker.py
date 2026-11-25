"""Read-only application update check against a user-configured JSON manifest."""
from __future__ import annotations

import json
import re
from urllib.error import URLError
from urllib.request import Request, urlopen


def _version_key(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(value or ""))
    if not parts:
        raise ValueError("Версия должна содержать цифры, например 8.1.0")
    return tuple(int(part) for part in parts)


def _is_newer(latest: str, current: str) -> bool:
    latest_key, current_key = _version_key(latest), _version_key(current)
    width = max(len(latest_key), len(current_key))
    return latest_key + (0,) * (width - len(latest_key)) > current_key + (0,) * (width - len(current_key))


def check_for_update(manifest_url: str, current_version: str, timeout: float = 5.0) -> dict:
    url = str(manifest_url or "").strip()
    if not url.lower().startswith("https://"):
        raise ValueError("Для манифеста обновлений укажите HTTPS-адрес.")
    request = Request(url, headers={"User-Agent": "GostDocumentGenerator-update-check"})
    try:
        with urlopen(request, timeout=timeout) as response:
            manifest = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Не удалось получить манифест обновлений: {exc}") from exc
    if not isinstance(manifest, dict) or not manifest.get("version"):
        raise ValueError("Манифест должен быть JSON-объектом с полем version.")
    latest = str(manifest["version"])
    available = _is_newer(latest, current_version)
    return {"available": available, "current_version": str(current_version),
            "latest_version": latest, "download_url": str(manifest.get("download_url", "")),
            "notes": str(manifest.get("notes", ""))}
