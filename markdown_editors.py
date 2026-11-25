"""Text-format helpers for the table and image insertion dialogs."""
import re


def _split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells, buffer, escaped = [], [], False
    for char in line:
        if escaped:
            buffer.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("".join(buffer).strip())
            buffer = []
        else:
            buffer.append(char)
    if escaped:
        buffer.append("\\")
    cells.append("".join(buffer).strip())
    return cells


def parse_markdown_table(text: str) -> list[list[str]] | None:
    rows = [line.strip() for line in (text or "").replace("\u2029", "\n").splitlines()
            if "|" in line and line.strip()]
    rows = [line for line in rows if not re.fullmatch(r"\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?", line)]
    parsed = [_split_row(line) for line in rows]
    if not parsed:
        return None
    width = max(map(len, parsed))
    return [row + [""] * (width - len(row)) for row in parsed]


def build_markdown_table(rows: list[list[str]], caption: str = "") -> str:
    cleaned = [[str(cell or "").replace("|", "\\|").replace("\n", " ").strip() for cell in row]
               for row in rows]
    if not cleaned or not max(map(len, cleaned)):
        raise ValueError("В таблице должна быть хотя бы одна строка и один столбец")
    width = max(map(len, cleaned))
    cleaned = [row + [""] * (width - len(row)) for row in cleaned]
    lines = []
    if caption.strip():
        lines.append(f"[TABLE: {caption.strip()}]")
    lines.append("| " + " | ".join(cleaned[0]) + " |")
    lines.append("| " + " | ".join("---" for _ in range(width)) + " |")
    lines.extend("| " + " | ".join(row) + " |" for row in cleaned[1:])
    return "\n".join(lines)


def parse_image_marker_options(text: str) -> tuple[str, str, float | None, str] | None:
    match = re.match(r"^\s*\[IMAGE:\s*(.*?)\]\s*$", text or "", re.IGNORECASE)
    if not match:
        return None
    parts = match.group(1).split(" | ")
    if len(parts) == 1:
        return "", parts[0].strip(), None, "center"
    path, caption = parts[0].strip(), parts[1].strip()
    options = {}
    for part in parts[2:]:
        if "=" in part:
            key, value = part.split("=", 1)
            options[key.strip().lower()] = value.strip()
    try:
        width = float(options["width"]) if "width" in options else None
    except ValueError:
        width = None
    if width is not None:
        width = max(2.0, min(20.0, width))
    alignment = options.get("align", "center").lower()
    if alignment not in ("left", "center", "right"):
        alignment = "center"
    return path, caption, width, alignment


def parse_image_marker(text: str) -> tuple[str, str] | None:
    parsed = parse_image_marker_options(text)
    return parsed[:2] if parsed else None


def build_image_marker(path: str, caption: str, width_cm: float = 15.0,
                       alignment: str = "center") -> str:
    if not str(path or "").strip():
        raise ValueError("Выберите файл изображения")
    alignment = alignment if alignment in ("left", "center", "right") else "center"
    return (f"[IMAGE: {str(path).strip()} | {str(caption or '').strip()} | "
            f"width={float(width_cm):g} | align={alignment}]")
