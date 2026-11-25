# processor/page_numbers.py
"""Нумерация страниц через поле PAGE в колонтитуле.
Word пересчитает номера сам."""
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def _make_page_field_run(paragraph):
    run = paragraph.add_run()
    r = run._r

    begin = OxmlElement('w:fldChar')
    begin.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = ' PAGE '
    sep = OxmlElement('w:fldChar')
    sep.set(qn('w:fldCharType'), 'separate')
    txt = OxmlElement('w:t')
    txt.text = '1'
    end = OxmlElement('w:fldChar')
    end.set(qn('w:fldCharType'), 'end')

    r.append(begin)
    r.append(instr)
    r.append(sep)
    r.append(txt)
    r.append(end)


def add_page_numbers(doc,
                     align=WD_ALIGN_PARAGRAPH.CENTER,
                     start_at=1,
                     skip_first_page=True,
                     position='footer'):
    """
    align: WD_ALIGN_PARAGRAPH.LEFT / CENTER / RIGHT
    start_at: с какого номера начинать (1 — стандартно)
    skip_first_page: True — на первой странице номера нет (титул)
    position: 'footer' или 'header'
    """
    for section in doc.sections:
        section.different_first_page_header_footer = skip_first_page

        # стираем номер на первой странице, если он там не нужен
        if skip_first_page:
            first = (section.first_page_header
                     if position == 'header'
                     else section.first_page_footer)
            for p in list(first.paragraphs):
                for r in list(p.runs):
                    r._r.getparent().remove(r._r)

        container = section.header if position == 'header' else section.footer
        p = container.paragraphs[0] if container.paragraphs else container.add_paragraph()
        p.alignment = align

        # очистка на случай повторного вызова
        for r in list(p.runs):
            r._r.getparent().remove(r._r)

        _make_page_field_run(p)

        # стартовый номер
        if start_at is not None:
            sectPr = section._sectPr
            pgNumType = sectPr.find(qn('w:pgNumType'))
            if pgNumType is None:
                pgNumType = OxmlElement('w:pgNumType')
                sectPr.append(pgNumType)
            pgNumType.set(qn('w:start'), str(start_at))