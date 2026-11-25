"""Check displayed image sizes in a generated DOCX."""
from docx import Document


def _effective_dpi(document, shape):
    try:
        rel_ids = shape._inline.xpath(".//a:blip/@r:embed")
        if not rel_ids or shape.width.inches <= 0 or shape.height.inches <= 0:
            return None
        image_part = document.part.related_parts.get(rel_ids[0])
        image = image_part.image if image_part is not None else None
        if image is None:
            return None
        return min(image.px_width / shape.width.inches,
                   image.px_height / shape.height.inches)
    except (AttributeError, KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def inspect_docx_images(path, min_width_cm: float = 2.0, min_dpi: float = 150.0) -> dict:
    document = Document(str(path))
    findings = []
    usable_width = min((section.page_width - section.left_margin - section.right_margin) / 360000
                       for section in document.sections)
    for index, shape in enumerate(document.inline_shapes, start=1):
        width, height = shape.width.cm, shape.height.cm
        if width < min_width_cm:
            findings.append({"code": "image_too_small", "index": index,
                             "message": f"Изображение {index} очень маленькое: {width:.1f} × {height:.1f} см."})
        if width > usable_width + 0.2:
            findings.append({"code": "image_too_large", "index": index,
                             "message": f"Изображение {index} шире рабочей области страницы ({width:.1f} см при доступных {usable_width:.1f} см)."})
        dpi = _effective_dpi(document, shape)
        if dpi is not None and dpi < min_dpi:
            findings.append({"code": "image_low_resolution", "index": index,
                             "message": f"Изображение {index} может выглядеть размытым: около {dpi:.0f} точек/дюйм при размещении (рекомендуется не менее {min_dpi:.0f})."})
    return {"count": len(document.inline_shapes), "findings": findings}


def format_image_report(report: dict) -> str:
    if not report["count"]:
        return "Проверка изображений: в документе нет встроенных изображений."
    if not report["findings"]:
        return f"Проверка изображений: {report['count']} изображений, критичных размеров не найдено."
    return f"Проверка изображений: найдено {len(report['findings'])} замечаний.\n" + "\n".join(
        item["message"] for item in report["findings"])
