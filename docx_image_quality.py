"""Check displayed image sizes in a generated DOCX."""
from docx import Document


def inspect_docx_images(path, min_width_cm: float = 2.0) -> dict:
    document = Document(str(path))
    findings = []
    usable_width = min((section.page_width - section.left_margin - section.right_margin).cm
                       for section in document.sections)
    for index, shape in enumerate(document.inline_shapes, start=1):
        width, height = shape.width.cm, shape.height.cm
        if width < min_width_cm:
            findings.append({"code": "image_too_small", "index": index,
                             "message": f"Изображение {index} очень маленькое: {width:.1f} × {height:.1f} см."})
        if width > usable_width + 0.2:
            findings.append({"code": "image_too_large", "index": index,
                             "message": f"Изображение {index} шире рабочей области страницы ({width:.1f} см при доступных {usable_width:.1f} см)."})
    return {"count": len(document.inline_shapes), "findings": findings}


def format_image_report(report: dict) -> str:
    if not report["count"]:
        return "Проверка изображений: в документе нет встроенных изображений."
    if not report["findings"]:
        return f"Проверка изображений: {report['count']} изображений, критичных размеров не найдено."
    return f"Проверка изображений: найдено {len(report['findings'])} замечаний.\n" + "\n".join(
        item["message"] for item in report["findings"])
