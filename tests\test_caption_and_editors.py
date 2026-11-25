import unittest

from caption_numbering import CaptionNumberer
from markdown_editors import (
    build_image_marker, build_markdown_table, parse_image_marker, parse_image_marker_options,
    parse_markdown_table,
)


class CaptionNumberingTests(unittest.TestCase):
    def test_numbers_figures_and_tables_independently(self):
        numberer = CaptionNumberer()
        self.assertEqual(numberer.format("figure", "Схема"), "Рисунок 1 — Схема")
        self.assertEqual(numberer.format("table", "Сравнение"), "Таблица 1 — Сравнение")
        self.assertEqual(numberer.format("image", "Фото"), "Рисунок 2 — Фото")

    def test_existing_number_advances_counter(self):
        numberer = CaptionNumberer()
        self.assertEqual(numberer.format("figure", "Рисунок 3.2 — Уже есть"),
                         "Рисунок 3.2 — Уже есть")
        self.assertEqual(numberer.format("figure", "Следующий"), "Рисунок 4 — Следующий")

    def test_disabled_numbering_preserves_caption(self):
        self.assertEqual(CaptionNumberer(False).format("table", " Таблица А "), "Таблица А")

    def test_appendices_use_cyrillic_letters(self):
        numberer = CaptionNumberer()
        self.assertEqual(numberer.format("appendix", "Материалы"), "Приложение А — Материалы")
        self.assertEqual(numberer.format("appendix", "Приложение В — Уже оформлено"),
                         "Приложение В — Уже оформлено")
        self.assertEqual(numberer.format("appendix", "Анкета"), "Приложение Г — Анкета")


class MarkdownEditorHelpersTests(unittest.TestCase):
    def test_table_round_trip_with_escaped_pipe_and_caption(self):
        source = build_markdown_table([["Имя", "Значение"], ["А", "x|y"]], "Проверка")
        self.assertIn("[TABLE: Проверка]", source)
        self.assertEqual(parse_markdown_table(source), [["Имя", "Значение"], ["А", "x|y"]])

    def test_image_marker_round_trip(self):
        marker = build_image_marker(r"C:\images\plot.png", "График", 12.5, "left")
        self.assertEqual(parse_image_marker(marker), (r"C:\images\plot.png", "График"))
        self.assertEqual(parse_image_marker_options(marker),
                         (r"C:\images\plot.png", "График", 12.5, "left"))

    def test_empty_table_is_rejected(self):
        with self.assertRaises(ValueError):
            build_markdown_table([])


if __name__ == "__main__":
    unittest.main()
