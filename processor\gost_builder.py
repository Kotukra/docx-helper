# processor/gost_builder.py

import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.part import XmlPart
from docx.opc.packuri import PackURI
from lxml import etree

try:
    from constants import PLACEHOLDER_IMAGE_PATH
except ImportError:
    PLACEHOLDER_IMAGE_PATH = "placeholder.png"

# ==========================================
# 1. СТИЛИ
# ==========================================
def setup_gost_styles(doc: Document, profile: dict | None = None):
    """Настраивает стили Word из активного профиля оформления."""
    profile = profile or {}
    body = {
        'font_name': profile.get('font_name', 'Times New Roman'),
        'font_size': float(profile.get('font_size', 14)),
        'alignment': profile.get('alignment', 'justify'),
        'line_spacing_multiple': float(profile.get('line_spacing_multiple', 1.5)),
        'first_line_indent': float(profile.get('first_line_indent', 1.25)),
        'space_before': float(profile.get('space_before', 0)),
        'space_after': float(profile.get('space_after', 0)),
    }
    alignments = {'left': WD_ALIGN_PARAGRAPH.LEFT, 'center': WD_ALIGN_PARAGRAPH.CENTER,
                  'right': WD_ALIGN_PARAGRAPH.RIGHT, 'justify': WD_ALIGN_PARAGRAPH.JUSTIFY}
    style_normal = doc.styles['Normal']
    style_normal.font.name = body['font_name']
    style_normal.font.size = Pt(body['font_size'])
    style_normal.element.rPr.rFonts.set(qn('w:eastAsia'), body['font_name'])
    pf = style_normal.paragraph_format
    pf.line_spacing = body['line_spacing_multiple']
    pf.first_line_indent = Cm(body['first_line_indent'])
    pf.alignment = alignments.get(body['alignment'], WD_ALIGN_PARAGRAPH.JUSTIFY)
    pf.space_before = Pt(body['space_before'])
    pf.space_after = Pt(body['space_after'])

    for style_name, key, defaults in (
        ('Heading 1', 'heading_1', {'font_name': body['font_name'], 'font_size': body['font_size'],
         'bold': True, 'alignment': 'center', 'space_before': 24, 'space_after': 12,
         'page_break_before': True}),
        ('Heading 2', 'heading_2', {'font_name': body['font_name'], 'font_size': body['font_size'],
         'bold': True, 'alignment': 'center', 'space_before': 12, 'space_after': 6,
         'page_break_before': False}),
        ('Heading 3', 'heading_3', {'font_name': body['font_name'], 'font_size': body['font_size'],
         'bold': True, 'alignment': 'left', 'space_before': 6, 'space_after': 3,
         'page_break_before': False}),
    ):
        conf = dict(defaults)
        conf.update(profile.get(key, {}))
        style = doc.styles[style_name]
        style.font.name = conf['font_name']
        style.font.size = Pt(float(conf['font_size']))
        style.font.bold = bool(conf.get('bold', True))
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.element.rPr.rFonts.set(qn('w:eastAsia'), conf['font_name'])
        hpf = style.paragraph_format
        hpf.alignment = alignments.get(conf.get('alignment', 'center'), WD_ALIGN_PARAGRAPH.CENTER)
        hpf.line_spacing = float(conf.get('line_spacing_multiple', body['line_spacing_multiple']))
        hpf.first_line_indent = Cm(float(conf.get('first_line_indent', 0)))
        hpf.space_before = Pt(float(conf.get('space_before', 0)))
        hpf.space_after = Pt(float(conf.get('space_after', 0)))
        hpf.page_break_before = bool(conf.get('page_break_before', False))
        hpf.keep_with_next = True

# ==========================================
# 2. СНОСКИ (Сложный путь через XML)
# ==========================================
def ensure_footnotes_part(doc: Document):
    """Создает часть footnotes.xml, если её нет в документе."""
    try:
        # Пытаемся найти существующую часть
        doc.part.part_related_by(RT.FOOTNOTES)
    except KeyError:
        # Создаем минимальный XML для сносок
        footnotes_xml = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            b'<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'<w:footnote w:type="separator" w:id="-1">'
            b'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
            b'<w:r><w:separator/></w:r></w:p></w:footnote>'
            b'<w:footnote w:type="continuationSeparator" w:id="0">'
            b'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
            b'<w:r><w:continuationSeparator/></w:r></w:p></w:footnote>'
            b'</w:footnotes>'
        )
        partname = PackURI('/word/footnotes.xml')
        content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml'
        element = etree.fromstring(footnotes_xml)
        part = XmlPart(partname, content_type, element, doc.part.package)
        doc.part.relate_to(part, RT.FOOTNOTES)

def add_real_footnote(paragraph, text: str):
    """Добавляет настоящую подстрочную сноску."""
    # Убедимся, что часть сносок существует
    ensure_footnotes_part(paragraph.part.document)

    # Исправлено: используем paragraph.part, а не paragraph.part.package
    footnotes_part = paragraph.part.part_related_by(RT.FOOTNOTES)
    footnotes_element = footnotes_part.element

    # Ищем максимальный ID
    existing_ids = []
    for fn in footnotes_element.findall(qn('w:footnote')):
        fid = fn.get(qn('w:id'))
        if fid is not None:
            existing_ids.append(int(fid))
    new_id = max(existing_ids) + 1 if existing_ids else 1

    # 1. Ссылка в тексте
    run = paragraph.add_run()
    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'separate')
    fldChar3 = OxmlElement('w:fldChar')
    fldChar3.set(qn('w:fldCharType'), 'end')

    footnote_ref = OxmlElement('w:footnoteReference')
    footnote_ref.set(qn('w:id'), str(new_id))

    run._r.append(fldChar1)
    run._r.append(fldChar2)
    run._r.append(footnote_ref)
    run._r.append(fldChar3)

    # 2. Сама сноска внизу
    footnote = OxmlElement('w:footnote')
    footnote.set(qn('w:id'), str(new_id))

    p = OxmlElement('w:p')
    pPr = OxmlElement('w:pPr')
    pStyle = OxmlElement('w:pStyle')
    pStyle.set(qn('w:val'), 'FootnoteText')
    pPr.append(pStyle)
    p.append(pPr)

    r = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), 'Times New Roman')
    rFonts.set(qn('w:hAnsi'), 'Times New Roman')
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), '24')  # 12 pt
    rPr.append(rFonts)
    rPr.append(sz)
    r.append(rPr)

    t = OxmlElement('w:t')
    t.text = text
    r.append(t)
    p.append(r)
    footnote.append(p)

    footnotes_element.append(footnote)

# ==========================================
# 3. КАРТИНКИ И ТАБЛИЦЫ
# ==========================================
def insert_image_placeholder(doc: Document, caption_text: str, width_cm: float = 15.0):
    """Вставляет картинку-заглушку и подпись под ней по ГОСТ."""
    if os.path.exists(PLACEHOLDER_IMAGE_PATH):
        try:
            doc.add_picture(PLACEHOLDER_IMAGE_PATH, width=Cm(width_cm))
            p_img = doc.paragraphs[-1]
        except Exception:
            p_img = doc.add_paragraph("[ОШИБКА ВСТАВКИ КАРТИНКИ]")
    else:
        p_img = doc.add_paragraph("[МЕСТО ДЛЯ РИСУНКА]")

    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.first_line_indent = Cm(0)
    p_img.paragraph_format.space_before = Pt(12)

    p_caption = doc.add_paragraph()
    p_caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_caption.paragraph_format.first_line_indent = Cm(0)
    p_caption.paragraph_format.space_after = Pt(12)
    run = p_caption.add_run(caption_text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(14)

def _set_repeat_table_header(row):
    """Повторяет строку заголовка таблицы на следующих страницах Word."""
    trPr = row._tr.get_or_add_trPr()
    tblHeader = OxmlElement('w:tblHeader')
    tblHeader.set(qn('w:val'), 'true')
    trPr.append(tblHeader)


def _prevent_row_split(row):
    """Не позволяет Word разрывать одну строку таблицы между страницами."""
    trPr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement('w:cantSplit')
    trPr.append(cant_split)


def add_gost_table(doc: Document, data: list, caption: str = None):
    """Создает компактную чёрно-белую таблицу; строки не разрываются."""
    if not data:
        return None

    if caption:
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p_cap.paragraph_format.first_line_indent = Cm(0)
        p_cap.paragraph_format.space_before = Pt(6)
        p_cap.paragraph_format.space_after = Pt(3)
        p_cap.paragraph_format.keep_with_next = True
        run = p_cap.add_run(caption)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(14)
        run.font.color.rgb = RGBColor(0, 0, 0)

    rows = len(data)
    cols = max((len(row) for row in data), default=0)
    if not cols:
        return None

    table = doc.add_table(rows=rows, cols=cols)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    # Чёткая чёрная сетка для печати без цветовых заливок.
    tblPr = table._tbl.tblPr
    borders = tblPr.find(qn('w:tblBorders'))
    if borders is None:
        borders = OxmlElement('w:tblBorders')
        tblPr.append(borders)
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        tag = 'w:' + edge
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn('w:val'), 'single')
        element.set(qn('w:sz'), '4')
        element.set(qn('w:space'), '0')
        element.set(qn('w:color'), '000000')

    for i, row_data in enumerate(data):
        row = table.rows[i]
        _prevent_row_split(row)
        if i == 0:
            _set_repeat_table_header(row)
        for j in range(cols):
            cell = row.cells[j]
            cell.text = str(row_data[j]) if j < len(row_data) and row_data[j] is not None else ''
            cell.vertical_alignment = 1  # CENTER
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                pf = paragraph.paragraph_format
                pf.first_line_indent = Cm(0)
                pf.left_indent = Cm(0)
                pf.right_indent = Cm(0)
                pf.line_spacing = 1.0
                pf.space_before = Pt(0)
                pf.space_after = Pt(0)
                pf.keep_together = True
                for run in paragraph.runs:
                    run.font.name = 'Times New Roman'
                    run.font.size = Pt(12)
                    run.font.color.rgb = RGBColor(0, 0, 0)
                    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), 'Times New Roman')
                    if i == 0:
                        run.bold = True

    # Небольшой отступ после таблицы без дополнительной пустой строки на полстраницы.
    p_after = doc.add_paragraph()
    p_after.paragraph_format.first_line_indent = Cm(0)
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(3)
    p_after.paragraph_format.line_spacing = 1.0
    p_after.paragraph_format.keep_together = True
    return table

# ==========================================
# 4. ОГЛАВЛЕНИЕ
# ==========================================
def add_table_of_contents(doc: Document):
    """Вставляет поле TOC (автособираемое оглавление)."""
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("СОДЕРЖАНИЕ")
    run.bold = True

    p_toc = doc.add_paragraph()
    run_toc = p_toc.add_run()

    fldChar = OxmlElement('w:fldChar')
    fldChar.set(qn('w:fldCharType'), 'begin')
    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = 'TOC \\o "1-3" \\h \\z \\u'
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'separate')
    text = OxmlElement('w:t')
    text.text = "Нажмите F9 для обновления оглавления"
    fldChar3 = OxmlElement('w:fldChar')
    fldChar3.set(qn('w:fldCharType'), 'end')

    run_toc._r.append(fldChar)
    run_toc._r.append(instrText)
    run_toc._r.append(fldChar2)
    run_toc._r.append(text)
    run_toc._r.append(fldChar3)
    p_toc.paragraph_format.first_line_indent = Cm(0)
    p_toc.paragraph_format.keep_together = True

    # Просим Word/LibreOffice обновить поле TOC при открытии документа.
    settings_el = doc.settings.element
    update_fields = settings_el.find(qn('w:updateFields'))
    if update_fields is None:
        update_fields = OxmlElement('w:updateFields')
        settings_el.append(update_fields)
    update_fields.set(qn('w:val'), 'true')

    doc.add_page_break()