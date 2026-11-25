from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from project_manager import ProjectManager


class ProjectManagerTests(unittest.TestCase):
    def test_project_round_trip_preserves_text_settings_and_id(self):
        with TemporaryDirectory() as tmp:
            manager = ProjectManager(tmp)
            saved = manager.save_project("Моя работа", "# Введение\nТекст", {
                "document_profile": "legacy_gost", "ppt_template_path": "template.pptx"})
            loaded = manager.load_project(saved["project_id"])
            self.assertEqual(loaded["name"], "Моя работа")
            self.assertEqual(loaded["text"], "# Введение\nТекст")
            self.assertEqual(loaded["settings"]["document_profile"], "legacy_gost")
            self.assertEqual(manager.list_projects()[0]["project_id"], saved["project_id"])

    def test_project_update_keeps_same_identity(self):
        with TemporaryDirectory() as tmp:
            manager = ProjectManager(tmp)
            first = manager.save_project("Черновик", "Первый текст", {})
            updated = manager.save_project("Черновик v2", "Новый текст", {}, first["project_id"])
            loaded = manager.load_project(first["project_id"])
            self.assertEqual(updated["project_id"], first["project_id"])
            self.assertEqual(loaded["name"], "Черновик v2")
            self.assertEqual(loaded["text"], "Новый текст")

    def test_recent_documents_deduplicate_and_keep_newest_first(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = ProjectManager(root / "data")
            first = root / "one.docx"
            second = root / "two.pptx"
            first.touch()
            second.touch()
            manager.record_document(str(first), "docx")
            manager.record_document(str(second), "pptx")
            manager.record_document(str(first), "docx")
            history = manager.recent_documents()
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]["path"], str(first))

    def test_invalid_project_id_and_empty_name_are_rejected(self):
        with TemporaryDirectory() as tmp:
            manager = ProjectManager(tmp)
            with self.assertRaises(ValueError):
                manager.load_project("../outside")
            with self.assertRaises(ValueError):
                manager.save_project(" ", "", {})


if __name__ == "__main__":
    unittest.main()
