import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from favorite_presets import FavoritePresetManager


class FavoritePresetTests(unittest.TestCase):
    def test_save_list_apply_and_delete(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "favorites.json"
            manager = FavoritePresetManager(path)
            manager.save("Учебная работа", {"document_profile": "jasmine", "font_size": 14,
                                             "ui_colors": {"accent": "#123456"}})
            self.assertEqual(manager.names(), ["Учебная работа"])
            self.assertEqual(manager.get("Учебная работа"),
                             {"document_profile": "jasmine", "font_size": 14})
            self.assertTrue(manager.delete("Учебная работа"))
            self.assertEqual(manager.names(), [])

    def test_rejects_empty_name_and_writes_valid_json(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "favorites.json"
            manager = FavoritePresetManager(path)
            with self.assertRaises(ValueError):
                manager.save("   ", {})
            manager.save("Короткий", {"ppt_max_items": 6})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["Короткий"]["ppt_max_items"], 6)


if __name__ == "__main__":
    unittest.main()
