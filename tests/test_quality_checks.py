import unittest

from quality_checks import detect_content, fix_safe_whitespace, format_report, inspect_text


class QualityChecksTests(unittest.TestCase):
    def test_detects_markdown_elements_and_presentation_markup(self):
        report = inspect_text("""# Введение
- пункт
| A | B |
|---|---|
```py
print(1)
```
[^сноска]
[SLIDE: title]
""")
        self.assertEqual(report["content_type"], "Разметка презентации")
        self.assertEqual(report["detected"]["markdown_headings"], 1)
        self.assertEqual(report["detected"]["lists"], 1)
        self.assertEqual(report["detected"]["tables"], 2)
        self.assertEqual(report["detected"]["footnotes"], 1)

    def test_structure_and_text_findings_are_reported(self):
        report = inspect_text("1.1 Раздел\n\nслово слово\n\n" + "а " * 20)
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("repeated_word", codes)
        self.assertIn("missing_introduction", codes)
        self.assertIn("missing_bibliography", codes)
        self.assertIn("Замечания", format_report(report))

    def test_empty_input_is_an_error(self):
        self.assertEqual(inspect_text(" ")["errors"], 1)

    def test_safe_whitespace_fix_preserves_markdown_source(self):
        text = "текст  \n\n\n\nдальше"
        self.assertEqual(fix_safe_whitespace(text), "текст\n\nдальше")
        self.assertEqual(fix_safe_whitespace(text, markdown_mode=True), text)

    def test_bibliography_section_reports_mixed_numbering(self):
        report = inspect_text("""СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ
1. Иванов И. И. Название книги. Москва, 2020.
Краткая ссылка
""")
        codes = {item["code"] for item in report["findings"]}
        self.assertEqual(report["bibliography_entries"], 2)
        self.assertIn("bibliography_numbering", codes)

    def test_bibliography_reports_number_gaps_and_repeats(self):
        report = inspect_text("""СПИСОК ИСТОЧНИКОВ
1. Автор. Название первого источника, 2020.
3. Автор. Название третьего источника, 2022.
""")
        self.assertIn("bibliography_sequence", {item["code"] for item in report["findings"]})

    def test_duplicate_fragments_are_reported(self):
        sentence = "Этот фрагмент текста повторяется в документе и содержит достаточно символов."
        report = inspect_text(sentence + "\n" + sentence)
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("duplicate_fragment", codes)
        self.assertEqual(len(report["duplicate_fragments"]), 1)

    def test_empty_bibliography_is_reported(self):
        report = inspect_text("СПИСОК ИСТОЧНИКОВ\n\nПРИЛОЖЕНИЕ А")
        self.assertIn("bibliography_empty", {item["code"] for item in report["findings"]})

    def test_markdown_bibliography_heading_is_detected(self):
        report = inspect_text("# Список использованных источников\n\n1. Полная запись источника.")
        self.assertTrue(report["detected"]["bibliography"])
        self.assertEqual(report["bibliography_entries"], 1)

    def test_chapters_and_appendices_are_detected(self):
        report = inspect_text("Введение\nГЛАВА 1 Основная часть\n[APPENDIX: Анкета]")
        self.assertTrue(report["detected"]["chapters"])
        self.assertTrue(report["detected"]["appendices"])

    def test_missing_chapters_and_appendices_are_reported_for_academic_work(self):
        report = inspect_text("ВВЕДЕНИЕ\n1.1 Раздел\nЗАКЛЮЧЕНИЕ\nСПИСОК ИСТОЧНИКОВ\nИсточник.")
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("missing_chapters", codes)
        self.assertIn("missing_appendices", codes)

    def test_gost_profile_geometry_and_text_settings_are_checked(self):
        from unittest.mock import patch
        bad_profile = {"page_width": 21, "page_height": 29.7,
                       "margins": {"left": 12, "right": 12, "top": 2, "bottom": 2},
                       "font_size": 100, "line_spacing_multiple": 4, "first_line_indent": 12}
        with patch("document_profile_manager.get_profile", return_value=bad_profile):
            report = inspect_text("Материал", {"document_profile": "bad_profile"})
        codes = {item["code"] for item in report["findings"]}
        self.assertTrue({"page_geometry_invalid", "font_size_invalid",
                         "line_spacing_invalid", "indent_invalid"}.issubset(codes))


class UpdateCheckerTests(unittest.TestCase):
    def test_github_manifest_matches_default_application_version(self):
        import json
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "updates.json").read_text(encoding="utf-8"))
        settings = json.loads((root / "default_settings.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], settings["app_version"])
        self.assertTrue(manifest["download_url"].startswith("https://"))
        self.assertEqual(settings["update_manifest_url"],
                         "https://raw.githubusercontent.com/Kotukra/docx-helper/main/updates.json")

    def test_manifest_version_comparison(self):
        import json
        from unittest.mock import patch
        from update_checker import check_for_update

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self):
                return json.dumps({"version": "8.2.0", "download_url": "https://example.org/app.zip"}).encode()

        with patch("update_checker.urlopen", return_value=Response()):
            result = check_for_update("https://example.org/releases.json", "8.1.0")
        self.assertTrue(result["available"])
        self.assertEqual(result["latest_version"], "8.2.0")

    def test_manifest_requires_https(self):
        from update_checker import check_for_update
        with self.assertRaises(ValueError):
            check_for_update("http://example.org/releases.json", "8.1.0")

    def test_manifest_rejects_non_https_release_link(self):
        import json
        from unittest.mock import patch
        from update_checker import check_for_update

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self):
                return json.dumps({"version": "8.2.0", "download_url": "http://example.org/app.zip"}).encode()

        with patch("update_checker.urlopen", return_value=Response()):
            with self.assertRaises(ValueError):
                check_for_update("https://example.org/releases.json", "8.1.0")

    def test_semver_trailing_zero_does_not_look_like_update(self):
        import json
        from unittest.mock import patch
        from update_checker import check_for_update

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self):
                return json.dumps({"version": "8.1.0"}).encode()

        with patch("update_checker.urlopen", return_value=Response()):
            result = check_for_update("https://example.org/releases.json", "8.1")
        self.assertFalse(result["available"])


if __name__ == "__main__":
    unittest.main()
