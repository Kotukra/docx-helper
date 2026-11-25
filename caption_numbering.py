"""Consistent sequential numbering for figure and table captions."""
import re


class CaptionNumberer:
    PREFIXES = {"figure": "Рисунок", "table": "Таблица", "appendix": "Приложение"}
    APPENDIX_LETTERS = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЭЮЯ"

    def __init__(self, enabled: bool = True):
        self.enabled = bool(enabled)
        self.counts = {"figure": 0, "table": 0, "appendix": 0}

    def format(self, kind: str, caption: str | None) -> str:
        kind = ("figure" if kind in ("figure", "image", "рисунок") else
                "table" if kind in ("table", "таблица") else "appendix")
        text = str(caption or "").strip()
        if not self.enabled:
            return text
        prefix = self.PREFIXES[kind]
        number_pattern = r"([А-ЯЁ])" if kind == "appendix" else r"(\d+(?:\.\d+)*)"
        existing = re.match(rf"^{prefix}\s+{number_pattern}\b", text, re.IGNORECASE)
        if existing:
            parsed = (self.APPENDIX_LETTERS.find(existing.group(1).upper()) + 1
                      if kind == "appendix" else int(existing.group(1).split(".")[0]))
            self.counts[kind] = max(self.counts[kind], parsed)
            return text
        text = re.sub(rf"^{prefix}\s*[:—–-]?\s*", "", text, flags=re.IGNORECASE)
        self.counts[kind] += 1
        number = self.counts[kind]
        label = (self.APPENDIX_LETTERS[number - 1]
                 if kind == "appendix" and number <= len(self.APPENDIX_LETTERS) else str(number))
        return f"{prefix} {label} — {text}" if text else f"{prefix} {label}"
