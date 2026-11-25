"""Lightweight text and structure inspection used before DOCX/PPTX generation."""
from __future__ import annotations

import re


_BIBLIOGRAPHY_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:список\s+(?:использованных\s+)?источников|библиография)\s*$",
    re.IGNORECASE,
)


def _bibliography_lines(text: str) -> list[str]:
    lines = (text or "").splitlines()
    start = next((index for index, line in enumerate(lines)
                  if _BIBLIOGRAPHY_HEADING.match(line)), None)
    if start is None:
        return []
    entries = []
    for line in lines[start + 1:]:
        stripped = line.strip()
        has_letters = any(char.isalpha() for char in stripped)
        is_upper_heading = has_letters and stripped == stripped.upper() and len(stripped) < 100
        if (re.match(r"^#{1,6}\s+", stripped)
                or re.match(r"^\d+(?:\.\d+)+\s+\S", stripped)
                or is_upper_heading):
            break
        if stripped:
            entries.append(stripped)
    return entries


def find_duplicate_fragments(text: str, min_length: int = 40) -> list[str]:
    """Return repeated sentence-sized fragments, ignoring case and whitespace."""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    seen = set()
    duplicates = []
    for sentence in sentences:
        display = re.sub(r"\s+", " ", sentence).strip()
        key = display.casefold()
        if len(display) >= min_length and key in seen and display not in duplicates:
            duplicates.append(display)
        seen.add(key)
    return duplicates


def inspect_gost_settings(settings: dict) -> list[dict]:
    from document_profile_manager import resolve_profile_settings

    resolved = resolve_profile_settings(settings)
    findings = []

    def add(code, message):
        findings.append({"severity": "warning", "code": code, "message": message})

    try:
        width, height = float(resolved.get("page_width", 21.0)), float(resolved.get("page_height", 29.7))
        margins = resolved.get("margins", {})
        horizontal = float(margins.get("left", 0)) + float(margins.get("right", 0))
        vertical = float(margins.get("top", 0)) + float(margins.get("bottom", 0))
        if width <= 0 or height <= 0 or horizontal >= width or vertical >= height:
            add("page_geometry_invalid", "Поля или размеры страницы оставляют нулевую рабочую область.")
        if min(float(margins.get(side, 0)) for side in ("left", "right", "top", "bottom")) < 0:
            add("negative_margin", "В профиле обнаружено отрицательное поле страницы.")
    except (TypeError, ValueError, AttributeError):
        add("page_geometry_invalid", "Не удалось проверить размеры страницы и поля выбранного профиля.")

    try:
        font_size = float(resolved.get("font_size", 14))
        if not 6 <= font_size <= 72:
            add("font_size_invalid", f"Основной размер шрифта {font_size:g} пт вне диапазона 6–72 пт.")
    except (TypeError, ValueError):
        add("font_size_invalid", "Основной размер шрифта должен быть числом.")
    try:
        spacing = float(resolved.get("line_spacing_multiple", 1.0))
        if not 0.8 <= spacing <= 3.0:
            add("line_spacing_invalid", f"Межстрочный интервал {spacing:g} вне диапазона 0,8–3,0.")
    except (TypeError, ValueError):
        add("line_spacing_invalid", "Межстрочный интервал должен быть числом.")
    try:
        indent = float(resolved.get("first_line_indent", 1.25))
        if not -2 <= indent <= 10:
            add("indent_invalid", f"Отступ первой строки {indent:g} см вне диапазона −2–10 см.")
    except (TypeError, ValueError):
        add("indent_invalid", "Отступ первой строки должен быть числом.")
    return findings


def detect_content(text: str) -> dict:
    lines = (text or "").splitlines()
    detected = {
        "presentation": bool(re.search(r"(?im)^\s*\[SLIDE:\s*\w+\]", text or "")),
        "markdown_headings": sum(bool(re.match(r"^\s{0,3}#{1,6}\s+\S", line)) for line in lines),
        "numbered_headings": sum(bool(re.match(r"^\s*\d+(?:\.\d+){0,5}[.)]?\s+\S", line)) for line in lines),
        "lists": sum(bool(re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", line)) for line in lines),
        "tables": sum(bool(re.match(r"^\s*\|.+\|\s*$", line)) for line in lines),
        "code_blocks": text.count("```") // 2 + text.count("~~~") // 2,
        "images": len(re.findall(r"(?im)^\s*(?:\[IMAGE:|!\[)", text or "")),
        "footnotes": len(re.findall(r"\[\^[^\]]+\]", text or "")),
        "bibliography": bool(re.search(r"(?im)^\s*(?:#{1,6}\s*)?(?:список\s+(?:использованных\s+)?источников|библиография)\s*$", text or "")),
        "chapters": bool(re.search(r"(?im)^\s*(?:#{1,6}\s*)?(?:глава\s+\d+\b|\d+\.\s+[А-ЯЁA-Z])", text or "")),
        "appendices": bool(re.search(r"(?im)^\s*(?:\[APPENDIX:|(?:#{1,6}\s*)?приложение(?:\s+[А-ЯЁA-Z0-9]+)?\s*$)", text or "")),
        "introduction": bool(re.search(r"(?im)^\s*(?:#\s*)?(?:введение|вступление)\s*$", text or "")),
        "conclusion": bool(re.search(r"(?im)^\s*(?:#\s*)?(?:заключение|выводы)\s*$", text or "")),
    }
    return detected


def inspect_text(text: str, settings: dict | None = None) -> dict:
    text = text or ""
    settings = settings or {}
    detected = detect_content(text)
    findings = []

    def add(severity, code, message):
        findings.append({"severity": severity, "code": code, "message": message})

    findings.extend(inspect_gost_settings(settings))

    if not text.strip():
        add("error", "empty", "Материал пустой.")
    if re.search(r"[^\S\r\n]{2,}", text):
        add("warning", "extra_spaces", "Найдены повторяющиеся пробелы внутри строк.")
    if re.search(r"\b([\wА-Яа-яЁё]+)(?:\s+\1\b)", text, re.IGNORECASE):
        add("warning", "repeated_word", "Возможно, рядом повторяется одно и то же слово.")

    paragraphs = [re.sub(r"\s+", " ", line).strip().casefold()
                  for line in text.splitlines() if line.strip()]
    seen = set()
    duplicates = set()
    for paragraph in paragraphs:
        if paragraph in seen and len(paragraph) >= 30:
            duplicates.add(paragraph)
        seen.add(paragraph)
    if duplicates:
        add("warning", "duplicate_paragraph", f"Найдены повторяющиеся абзацы: {len(duplicates)}.")
    duplicate_fragments = find_duplicate_fragments(text)
    if duplicate_fragments:
        sample = " · ".join(fragment[:90] for fragment in duplicate_fragments[:3])
        add("warning", "duplicate_fragment",
            f"Найдены повторяющиеся фрагменты: {len(duplicate_fragments)}. Примеры: {sample}")

    bibliography_entries = _bibliography_lines(text)
    if detected["bibliography"]:
        if not bibliography_entries:
            add("warning", "bibliography_empty", "Раздел библиографии найден, но список источников пуст.")
        else:
            numbered = [bool(re.match(r"^(?:\[\d+\]|\d+[.)])\s*\S", item))
                        for item in bibliography_entries]
            if any(numbered) and not all(numbered):
                add("warning", "bibliography_numbering",
                    "В списке источников смешаны нумерованные и ненумерованные записи.")
            elif numbered and all(numbered):
                numbers = []
                for item in bibliography_entries:
                    match = re.match(r"^(?:\[(\d+)\]|(\d+)[.)])", item)
                    numbers.append(int(match.group(1) or match.group(2)))
                if numbers != list(range(1, len(numbers) + 1)):
                    add("warning", "bibliography_sequence",
                        "Нумерация источников содержит повторные номера или пропуски.")
            if any(len(item) < 12 for item in bibliography_entries):
                add("warning", "bibliography_short_entry",
                    "В библиографии есть слишком короткая запись; проверьте её полноту.")

    if detected["presentation"]:
        content_type = "Разметка презентации"
    elif detected["markdown_headings"] or detected["tables"] or detected["code_blocks"]:
        content_type = "Структурированный текст / Markdown"
    elif detected["numbered_headings"] or detected["introduction"] or detected["conclusion"]:
        content_type = "Учебная или отчётная работа"
    else:
        content_type = "Обычный текст"

    if (detected["numbered_headings"] or detected["introduction"] or detected["conclusion"]):
        if not detected["introduction"]:
            add("info", "missing_introduction", "Не распознано введение; проверьте структуру работы.")
        if not detected["conclusion"]:
            add("info", "missing_conclusion", "Не распознано заключение; проверьте структуру работы.")
        if not detected["bibliography"]:
            add("info", "missing_bibliography", "Не распознан раздел списка источников.")
        if not detected["chapters"]:
            add("info", "missing_chapters", "Главы не распознаны; проверьте, требуется ли деление на главы.")
        if not detected["appendices"]:
            add("info", "missing_appendices", "Приложения не распознаны; проверьте, требуются ли они для работы.")

    profile_id = settings.get("document_profile", "jasmine")
    if profile_id not in ("jasmine", "legacy_gost") and not settings.get("_document_style_profile"):
        add("warning", "profile_missing", f"Профиль «{profile_id}» не найден; будет применён резервный профиль.")

    return {
        "content_type": content_type,
        "detected": detected,
        "findings": findings,
        "bibliography_entries": len(bibliography_entries),
        "duplicate_fragments": duplicate_fragments,
        "errors": sum(item["severity"] == "error" for item in findings),
        "warnings": sum(item["severity"] == "warning" for item in findings),
    }


def format_report(report: dict) -> str:
    detected = report.get("detected", {})
    labels = {
        "markdown_headings": "заголовки", "numbered_headings": "нумерованные разделы",
        "lists": "элементы списков", "tables": "строки таблиц", "code_blocks": "блоки кода",
        "images": "изображения", "footnotes": "сноски", "chapters": "главы",
        "appendices": "приложения",
    }
    parts = [f"Определённый тип материала: {report.get('content_type', 'не определён')}"]
    elements = [f"{label}: {detected.get(key, 0)}" for key, label in labels.items() if detected.get(key)]
    parts.append("Обнаружено: " + ("; ".join(elements) if elements else "специальная разметка не обнаружена"))
    findings = report.get("findings", [])
    if findings:
        parts.append("\nЗамечания:")
        parts.extend(f"[{item['severity'].upper()}] {item['message']}" for item in findings)
    else:
        parts.append("\nЗамечаний не найдено.")
    return "\n".join(parts)


def fix_safe_whitespace(text: str, markdown_mode: bool = False) -> str:
    """Apply conservative whitespace cleanup without changing Markdown syntax."""
    if markdown_mode:
        return text
    cleaned = []
    blank_run = 0
    in_code = False
    for original in (text or "").splitlines():
        is_fence = original.lstrip().startswith(("```", "~~~"))
        if is_fence:
            in_code = not in_code
        line = original if in_code else original.rstrip()
        if not in_code and not line.strip():
            blank_run += 1
            if blank_run > 1:
                continue
        else:
            blank_run = 0
        cleaned.append(line)
    return "\n".join(cleaned).strip()
