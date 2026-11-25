import unittest

from processor.keywords import split_text_by_marker


class BatchSplittingTests(unittest.TestCase):
    def test_split_marker_is_ignored_when_batch_split_is_disabled(self):
        source = "Первая часть\n---\nВторая часть"
        self.assertEqual(split_text_by_marker(source, "---", enabled=False), [source])

    def test_enabled_split_returns_nonempty_parts(self):
        self.assertEqual(split_text_by_marker(" Первая \n---\n Вторая ", "---"),
                         ["Первая", "Вторая"])


if __name__ == "__main__":
    unittest.main()
