"""Export a portable backup of application settings, profiles, and projects."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import zipfile


class BackupManager:
    def __init__(self, app_root: Path | str, user_data: Path | str,
                 settings_files: tuple[Path | str, ...] = (),
                 profile_dir: Path | str | None = None,
                 autosave_file: Path | str | None = None):
        self.app_root = Path(app_root)
        self.user_data = Path(user_data)
        self.settings_files = tuple(Path(path) for path in settings_files)
        self.profile_dir = Path(profile_dir) if profile_dir else self.app_root / "profiles"
        self.autosave_file = Path(autosave_file) if autosave_file else None

    def create_backup(self, destination: Path | str) -> list[str]:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination_resolved = destination.resolve()
        included = []
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for settings_file in self.settings_files:
                if settings_file.is_file():
                    archive.write(settings_file, f"settings/{settings_file.name}")
                    included.append(f"settings/{settings_file.name}")
            if self.profile_dir.is_dir():
                for path in sorted(self.profile_dir.glob("*.json")):
                    name = f"profiles/{path.name}"
                    archive.write(path, name)
                    included.append(name)
            if self.user_data.is_dir():
                for path in sorted(self.user_data.rglob("*")):
                    if not path.is_file():
                        continue
                    if path.resolve() == destination_resolved:
                        continue
                    name = (Path("user_data") / path.relative_to(self.user_data)).as_posix()
                    archive.write(path, name)
                    included.append(name)
            if self.autosave_file and self.autosave_file.is_file():
                archive.write(self.autosave_file, "autosave.json")
                included.append("autosave.json")
            manifest = {
                "format": "gost-document-generator-backup-v1",
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "files": included,
            }
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        return included
