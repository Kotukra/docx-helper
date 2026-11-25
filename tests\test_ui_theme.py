import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from settings_manager import SettingsManager
from ui_theme import BUILTIN_PALETTES, DEFAULT_COLORS, normalize_colors, normalize_palettes


class UiThemeTests(unittest.TestCase):
    def test_builtin_palettes_have_valid_complete_colors(self):
        self.assertEqual(normalize_colors(), DEFAULT_COLORS)
        for palette in BUILTIN_PALETTES.values():
            self.assertEqual(set(normalize_colors(palette["colors"])), set(DEFAULT_COLORS))

    def test_legacy_accent_is_migrated_without_touching_document_profile(self):
        manager = SettingsManager()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(json.dumps({"accent_color": "#123abc", "document_profile": "legacy_gost"}),
                            encoding="utf-8")
            self.assertTrue(manager.load_from_file(str(path)))
        self.assertEqual(manager.get("ui_colors")["accent"], "#123abc")
        self.assertEqual(manager.get("document_profile"), "legacy_gost")

    def test_custom_palette_validation_and_case_insensitive_deduplication(self):
        palettes = normalize_palettes([
            {"name": "My colors", "colors": DEFAULT_COLORS},
            {"name": "my COLORS", "colors": {"accent": "#ffffff"}},
        ])
        self.assertEqual(len(palettes), 1)
        self.assertEqual(palettes[0]["name"], "My colors")
        with self.assertRaises(ValueError):
            normalize_colors({"accent": "purple"})


if __name__ == "__main__":
    unittest.main()
