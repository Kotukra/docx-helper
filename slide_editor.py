"""Round-trip conversion between slide data and editable generator markup."""
from __future__ import annotations

SLIDE_TYPES = ("title", "bullets", "section", "image", "image_right", "image_left",
               "image_full", "table", "chart", "conclusion")


def serialize_presentation(slides: list[dict]) -> str:
    blocks = []
    for slide in slides:
        lines = [f"[SLIDE: {slide.get('type', 'bullets')}]"]
        if slide.get("title"):
            lines.append(f"# {slide['title']}")
        if slide.get("subtitle"):
            lines.append(f"[SUB: {slide['subtitle']}]")
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
