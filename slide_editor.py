"""Round-trip conversion between slide data and editable generator markup."""
from __future__ import annotations

import math

SLIDE_TYPES = ("title", "bullets", "section", "image", "image_right", "image_left",
               "image_full", "table", "chart", "conclusion")


def normalize_slide_positions(positions):
    """Keep only normalized x/y/width/height boxes fully inside the slide."""
    if not isinstance(positions, dict):
        return {}
    normalized = {}
    for key, box in positions.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        try:
            x, y, width, height = (float(value) for value in box)
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in (x, y, width, height)):
            continue
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
            continue
        normalized[key.strip()] = (x, y, width, height)
    return normalized


def parse_slide_positions(markup: str):
    """Parse `[LAYOUT: title=x,y,w,h; body=x,y,w,h]` metadata."""
    positions = {}
    for line in markup.splitlines():
        line = line.strip()
        if not (line.startswith("[LAYOUT:") and line.endswith("]")):
            continue
        payload = line[len("[LAYOUT:"):-1]
        for item in payload.split(";"):
            if "=" not in item:
                continue
            key, raw_box = item.split("=", 1)
            try:
                box = tuple(float(value.strip()) for value in raw_box.split(","))
            except ValueError:
                continue
            if len(box) == 4:
                positions[key.strip()] = box
    return normalize_slide_positions(positions)


def format_slide_positions(positions):
    normalized = normalize_slide_positions(positions)
    return "; ".join(
        f"{key}=" + ",".join(f"{value:.4f}" for value in box)
        for key, box in normalized.items()
    )


def serialize_presentation(slides: list[dict]) -> str:
    blocks = []
    for slide in slides:
        lines = [f"[SLIDE: {slide.get('type', 'bullets')}]"]
        if slide.get("title"):
            lines.append(f"# {slide['title']}")
        if slide.get("subtitle"):
            lines.append(f"[SUB: {slide['subtitle']}]")
        layout = format_slide_positions(slide.get("positions", {}))
        if layout:
            lines.append(f"[LAYOUT: {layout}]")
        for level, text in slide.get("bullets", []):
            lines.append(f"{'  ' * max(0, int(level))}- {text}")
        for image in slide.get("images", []):
            lines.append(f"[IMAGE: {image}]")
        chart = slide.get("chart")
        if chart:
            lines.extend([f"[CHART: {chart.get('kind', 'bar')}]", chart.get("data", ""), "[/CHART]"])
        table = slide.get("table")
        if table:
            lines.append("[TABLE]")
            lines.extend("| " + " | ".join(row) + " |" for row in table)
            lines.append("[/TABLE]")
        if slide.get("notes"):
            lines.append(f"[NOTES: {slide['notes']}]")
        blocks.append("\n".join(lines))
    return "\n---\n".join(blocks)

