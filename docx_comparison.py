"""Compare key layout properties of a generated DOCX with a reference."""
from __future__ import annotations

from collections import Counter
from docx import Document


def _font_signature(document):
    fonts = Counter()
    sizes = Counter()
    for paragraph in document.paragraphs:
        if paragraph.style and paragraph.style.name.startswith("Heading"):
            continue
        for run in paragraph.runs:
            if not run.text.strip():
                continue
            if run.font.name:
                fonts[run.font.name] += len(run.text)
            if run.font.size:
                sizes[round(run.font.size.pt, 1)] += len(run.text)
    normal = document.styles["Normal"].font
    return (fonts.most_common(1)[0][0] if fonts else normal.name,
            sizes.most_common(1)[0][0] if sizes else (round(normal.size.pt, 1) if normal.size else None))


def _table_signature(document):
    return [(len(table.rows), len(table.columns)) for table in document.tables]


def compare_docx(reference_path, candidate_path, tolerance_cm: float = 0.2) -> dict:
    reference = Document(str(reference_path))
    candidate = Document(str(candidate_path))
    findings = []

    def compare(name, left, right, tolerance=0):
        if abs(left - right) > tolerance:
            findings.append({"property": name, "reference": left, "candidate": right})

    ref_section = reference.sections[0]
    cand_section = candidate.sections[0]
    for name in ("page_width", "page_height", "top_margin", "bottom_margin", "left_margin", "right_margin"):
        compare(name, getattr(ref_section, name).cm, getattr(cand_section, name).cm, tolerance_cm)
    ref_font = _font_signature(reference)
    cand_font = _font_signature(candidate)
    if ref_font[0] and cand_font[0] and ref_font[0] != cand_font[0]:
        findings.append({"property": "font_name", "reference": ref_font[0], "candidate": cand_font[0]})
    if ref_font[1] and cand_font[1] and abs(ref_font[1] - cand_font[1]) > 1.0:
        findings.append({"property": "font_size_pt", "reference": ref_font[1], "candidate": cand_font[1]})
    for style_name in ("Normal", "Heading 1", "Heading 2", "Heading 3"):
        if (style_name not in {style.name for style in reference.styles}
                or style_name not in {style.name for style in candidate.styles}):
            continue
        ref_style = reference.styles[style_name]
        cand_style = candidate.styles[style_name]
        for property_name, ref_value, cand_value in (
            (f"{style_name}.line_spacing", ref_style.paragraph_format.line_spacing,
             cand_style.paragraph_format.line_spacing),
            (f"{style_name}.space_before_pt", ref_style.paragraph_format.space_before.pt
             if ref_style.paragraph_format.space_before else None,
             cand_style.paragraph_format.space_before.pt if cand_style.paragraph_format.space_before else None),
            (f"{style_name}.space_after_pt", ref_style.paragraph_format.space_after.pt
             if ref_style.paragraph_format.space_after else None,
             cand_style.paragraph_format.space_after.pt if cand_style.paragraph_format.space_after else None),
            (f"{style_name}.alignment", str(ref_style.paragraph_format.alignment),
             str(cand_style.paragraph_format.alignment)),
            (f"{style_name}.font_name", ref_style.font.name, cand_style.font.name),
            (f"{style_name}.font_size_pt", ref_style.font.size.pt if ref_style.font.size else None,
             cand_style.font.size.pt if cand_style.font.size else None),
        ):
            if ref_value is not None and cand_value is not None and ref_value != cand_value:
                findings.append({"property": property_name, "reference": ref_value, "candidate": cand_value})
    ref_tables, cand_tables = _table_signature(reference), _table_signature(candidate)
    if ref_tables != cand_tables:
        findings.append({"property": "table_dimensions", "reference": ref_tables,
                         "candidate": cand_tables})
    return {"reference": str(reference_path), "candidate": str(candidate_path),
            "findings": findings, "matches": not findings}


def format_comparison(report: dict) -> str:
    if report["matches"]:
        return "Основные параметры оформления совпадают с образцом."
    labels = {"page_width": "ширина страницы", "page_height": "высота страницы",
              "top_margin": "верхнее поле", "bottom_margin": "нижнее поле",
              "left_margin": "левое поле", "right_margin": "правое поле",
              "font_name": "основной шрифт", "font_size_pt": "размер шрифта",
              "table_count": "количество таблиц", "table_dimensions": "размеры таблиц"}
    return "Обнаружены различия (образец → проверяемый документ):\n" + "\n".join(
        f"• {labels.get(item['property'], item['property'])}: "
        f"{item['reference']} → {item['candidate']}" for item in report["findings"])
