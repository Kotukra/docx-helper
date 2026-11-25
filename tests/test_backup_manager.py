import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import unittest

from backup_manager import BackupManager


class BackupManagerTests(unittest.TestCase):
    def test_backup_contains_settings_profiles_projects_and_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = root / "document_settings.json"
            settings.write_text('{"document_profile":"legacy_gost"}', encoding="utf-8")
            profiles = root / "profiles"
            profiles.mkdir()
            (profiles / "custom.json").write_text('{"profile_id":"custom"}', encoding="utf-8")
            user_data = root / "user_data"
            projects = user_data / "projects"
            projects.mkdir(parents=True)
            (projects / "one.json").write_text('{"name":"one"}', encoding="utf-8")
            history = user_data / "recent_documents.json"
            history.write_text('{"items":[]}', encoding="utf-8")
            autosave = root / "autosave.json"
            autosave.write_text('{"text":"draft"}', encoding="utf-8")
            destination = root / "backup.zip"
            manager = BackupManager(root, user_data, (settings,), profiles, autosave)

            included = manager.create_backup(destination)
            self.assertIn("settings/document_settings.json", included)
            self.assertIn("profiles/custom.json", included)
            with ZipFile(destination) as archive:
                self.assertIsNone(archive.testzip())
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(manifest["format"], "gost-document-generator-backup-v1")
                self.assertIn("user_data/projects/one.json", archive.namelist())
                self.assertIn("autosave.json", archive.namelist())


if __name__ == "__main__":
    unittest.main()
