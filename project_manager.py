"""Named project storage and recent output history."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import uuid


def _default_data_dir() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "GostDocumentGenerator"


class ProjectManager:
    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir else _default_data_dir()
        self.projects_dir = self.data_dir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.history_path = self.data_dir / "recent_documents.json"

    def _project_path(self, project_id: str) -> Path:
        try:
            safe_id = str(uuid.UUID(str(project_id)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("Некорректный идентификатор проекта") from exc
        return self.projects_dir / f"{safe_id}.json"

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.stem}_", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        except Exception:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise

    def save_project(self, name: str, text: str, settings: dict,
                     project_id: str | None = None) -> dict:
        name = str(name or "").strip()
        if not name:
            raise ValueError("Укажите название проекта")
        if not isinstance(settings, dict):
            raise ValueError("Настройки проекта должны быть объектом")
        project_id = str(uuid.UUID(str(project_id))) if project_id else str(uuid.uuid4())
        record = {
            "schema_version": 1,
            "project_id": project_id,
            "name": name[:120],
            "text": str(text or ""),
            "settings": deepcopy(settings),
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        self._write_json(self._project_path(project_id), record)
        return {key: record[key] for key in ("project_id", "name", "updated_at")}

    def load_project(self, project_id: str) -> dict:
        path = self._project_path(project_id)
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, dict) or not isinstance(data.get("settings"), dict):
            raise ValueError("Файл проекта повреждён")
        return data

    def list_projects(self) -> list[dict]:
        result = []
        for path in self.projects_dir.glob("*.json"):
            try:
                with path.open("r", encoding="utf-8") as stream:
                    data = json.load(stream)
                if isinstance(data, dict) and data.get("project_id"):
                    result.append({key: data.get(key) for key in ("project_id", "name", "updated_at")})
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(result, key=lambda item: item.get("updated_at") or "", reverse=True)

    def record_document(self, path: str, kind: str) -> None:
        full_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(full_path):
            return
        try:
            with self.history_path.open("r", encoding="utf-8") as stream:
                stored = json.load(stream)
            history = stored.get("items", []) if isinstance(stored, dict) else stored
            if not isinstance(history, list):
                history = []
        except (OSError, json.JSONDecodeError):
            history = []
        normalized = os.path.normcase(full_path)
        history = [item for item in history if isinstance(item, dict)
                   and os.path.normcase(os.path.abspath(item.get("path", ""))) != normalized]
        history.insert(0, {"path": full_path, "kind": str(kind),
                           "created_at": datetime.now().astimezone().isoformat(timespec="seconds")})
        self._write_json(self.history_path, {"items": history[:50]})

    def recent_documents(self) -> list[dict]:
        try:
            with self.history_path.open("r", encoding="utf-8") as stream:
                data = json.load(stream)
            items = data.get("items", []) if isinstance(data, dict) else []
            return [item for item in items if isinstance(item, dict) and item.get("path")]
        except (OSError, json.JSONDecodeError):
            return []
