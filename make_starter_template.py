# make_starter_template.py
"""
Генерирует starter.pptx с дефолтными layout-ами PowerPoint.
Запуск:
    python make_starter_template.py [папка]
По умолчанию создаёт templates_ppt/starter.pptx.
"""
import os
import sys
from pptx import Presentation


def make_starter_template(folder: str = "templates_ppt", name: str = "starter.pptx") -> str:
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)

    prs = Presentation()

    # Удаляем все существующие слайды, чтобы шаблон был пустым
    sldIdLst = prs.slides._sldIdLst
    for slide_id in list(sldIdLst):
        rId = slide_id.rId
        prs.part.drop_rel(rId)
        sldIdLst.remove(slide_id)

    prs.save(path)
    return path


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "templates_ppt"
    out = make_starter_template(folder)
    print(f"Шаблон создан: {out}")
    print("Layout-ы: стандартные (Title Slide, Title and Content, Section Header, Two Content, ...)")