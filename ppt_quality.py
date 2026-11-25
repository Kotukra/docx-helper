"""Structural quality checks for generated PowerPoint presentations."""
from __future__ import annotations

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


def inspect_presentation(path, min_font_pt: float = 10.0) -> dict:
    prs = Presentation(str(path))
    findings = []
    width, height = prs.slide_width, prs.slide_height
    for slide_index, slide in enumerate(prs.slides, start=1):
        text_shapes = []
        for shape_index, shape in enumerate(slide.shapes, start=1):
            if shape.left < 0 or shape.top < 0 or shape.left + shape.width > width or shape.top + shape.height > height:
                findings.append({"slide": slide_index, "code": "out_of_bounds",
                                 "message": f"Элемент {shape_index} выходит за границы слайда."})
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE and min(shape.width, shape.height) < 2 * 360000:
                findings.append({"slide": slide_index, "code": "small_image",
                                 "message": f"Изображение {shape_index} слишком маленькое и может быть плохо различимо."})
            if not getattr(shape, "has_text_frame", False):
                continue
            text = shape.text.strip()
            if text:
                text_shapes.append((shape_index, shape, text))
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    size = run.font.size
                    if size is not None and size.pt < min_font_pt and run.text.strip():
                        findings.append({"slide": slide_index, "code": "small_font",
                                         "message": f"Текст на элементе {shape_index}: {size.pt:g} пт, меньше {min_font_pt:g} пт."})
        for left_idx, (shape_index, first, _first_text) in enumerate(text_shapes):
            for other_index, second, _second_text in text_shapes[left_idx + 1:]:
                overlap_w = max(0, min(first.left + first.width, second.left + second.width) - max(first.left, second.left))
                overlap_h = max(0, min(first.top + first.height, second.top + second.height) - max(first.top, second.top))
                smaller_area = min(first.width * first.height, second.width * second.height)
                if smaller_area and overlap_w * overlap_h / smaller_area >= 0.25:
                    findings.append({"slide": slide_index, "code": "text_overlap",
                                     "message": f"Текстовые элементы {shape_index} и {other_index} заметно перекрываются."})
    return {"slides": len(prs.slides), "findings": findings,
            "errors": sum(item["code"] == "out_of_bounds" for item in findings),
            "warnings": sum(item["code"] != "out_of_bounds" for item in findings)}


def format_presentation_report(report: dict, max_findings: int = 12) -> str:
    findings = report.get("findings", [])
    lines = [f"Проверка слайдов: {report.get('slides', 0)} слайдов; "
             f"выходов за границы: {report.get('errors', 0)}; замечаний: {report.get('warnings', 0)}."]
    lines.extend(f"Слайд {item['slide']}: {item['message']}" for item in findings[:max_findings])
    if len(findings) > max_findings:
        lines.append(f"Ещё замечаний: {len(findings) - max_findings}.")
    return "\n".join(lines)
