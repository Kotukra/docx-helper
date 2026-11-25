# processor/ppt_builder.py
import os
from datetime import datetime
from PIL import Image
from pptx.util import Pt, Cm
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR


# ---------- Layouts ----------
def find_layout_by_name(prs, name):
    if not name:
        return _fallback_layout(prs)
    for layout in prs.slide_layouts:
        if layout.name and layout.name.lower() == name.lower():
            return layout
    nl = name.lower()
    for layout in prs.slide_layouts:
        if layout.name and nl in layout.name.lower():
            return layout
    return _fallback_layout(prs)


def _fallback_layout(prs):
    if len(prs.slide_layouts) > 1:
        return prs.slide_layouts[1]
    return prs.slide_layouts[0]


# ---------- Title / Subtitle / Body ----------
def set_title(slide, text, prs):
    if not text:
        return
    title_ph = slide.shapes.title
    if title_ph is not None:
        title_ph.text = text
        return
    tb = slide.shapes.add_textbox(Cm(1), Cm(0.8), prs.slide_width - Cm(2), Cm(2.5))
    tb.text_frame.text = text
    for run in tb.text_frame.paragraphs[0].runs:
        run.font.size = Pt(32)
        run.font.bold = True


def try_set_subtitle(slide, text):
    if not text:
        return False
    for ph in slide.placeholders:
        try:
            idx = ph.placeholder_format.idx
        except Exception:
            idx = -1
        if idx == 1:
            try:
                ph.text = text
                return True
            except Exception:
                continue
    return False


def find_body_placeholder(slide):
    for ph in slide.placeholders:
        try:
            idx = ph.placeholder_format.idx
        except Exception:
            idx = -1
        if idx == 1:
            return ph
    return None


# ---------- Bullets ----------
def add_bullets_auto(placeholder, bullets, base_size=28, min_size=14):
    tf = placeholder.text_frame
    tf.clear()
    tf.word_wrap = True

    total_chars = sum(len(t) for _, t in bullets)
    n = len(bullets)

    size = base_size
    checks = [
        (n > 6, 4),
        (n > 9, 4),
        (n > 12, 4),
        (total_chars > 400, 4),
        (total_chars > 700, 4),
        (total_chars > 1100, 4),
    ]
    for condition, delta in checks:
        if condition:
            size = max(min_size, size - delta)

    for i, (level, text) in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = text
        p.level = min(int(level), 4)
        run_size = max(min_size, size - 4 * level)
        for run in p.runs:
            run.font.size = Pt(run_size)


# ---------- Images ----------
def _fit_image_box(path, max_width, max_height):
    """Возвращает размеры изображения, вписанного в область без искажения."""
    with Image.open(path) as img:
        image_width, image_height = img.size
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Некорректные размеры изображения")
    scale = min(max_width / image_width, max_height / image_height)
    return int(image_width * scale), int(image_height * scale)


def add_image_or_placeholder(slide, images, prs, side='right'):
    path = images[0] if images else None
    sw = prs.slide_width
    sh = prs.slide_height

    if side == 'right':
        left = int(sw * 0.55)
    elif side == 'left':
        left = int(sw * 0.05)
    else:
        left = int(sw * 0.05)
    top = int(sh * 0.18)
    width = int(sw * 0.40)
    height = int(sh * 0.65)

    if path and os.path.exists(path):
        try:
            fitted_w, fitted_h = _fit_image_box(path, width, height)
            fitted_left = left + (width - fitted_w) // 2
            fitted_top = top + (height - fitted_h) // 2
            return slide.shapes.add_picture(path, fitted_left, fitted_top, width=fitted_w, height=fitted_h)
        except Exception:
            pass

    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = f"[МЕСТО ДЛЯ КАРТИНКИ]\n\n{path or '(путь не указан)'}"
    for p in tf.paragraphs:
        for run in p.runs:
            run.font.size = Pt(14)
    return tb


def add_full_image(slide, images, prs):
    path = images[0] if images else None
    if path and os.path.exists(path):
        try:
            fitted_w, fitted_h = _fit_image_box(path, prs.slide_width, prs.slide_height)
            left = (prs.slide_width - fitted_w) // 2
            top = (prs.slide_height - fitted_h) // 2
            return slide.shapes.add_picture(path, left, top, width=fitted_w, height=fitted_h)
        except Exception:
            pass
    tb = slide.shapes.add_textbox(0, 0, prs.slide_width, prs.slide_height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = f"[КАРТИНКА НА ВЕСЬ СЛАЙД]\n\n{path or '(путь не указан)'}"
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for p in tf.paragraphs:
        p.alignment = PP_ALIGN.CENTER
        for run in p.runs:
            run.font.size = Pt(20)
    return tb


# ---------- Table ----------
def add_table(slide, rows, prs):
    if not rows:
        return
    n_rows = len(rows)
    n_cols = max(len(r) for r in rows)
    left = Cm(1.5)
    top = Cm(4)
    width = prs.slide_width - Cm(3)
    # Оставляем нижнее поле слайда и не даём таблице выйти за его границы.
    bottom_margin = Cm(1.2)
    available_height = max(Cm(3), prs.slide_height - top - bottom_margin)
    height = min(Cm(1.55) * n_rows, available_height)
    row_height = int(height / n_rows)

    shape = slide.shapes.add_table(n_rows, n_cols, left, top, width, height)
    table = shape.table
    for row in table.rows:
        row.height = row_height
    for i, row in enumerate(rows):
        for j in range(n_cols):
            text = row[j] if j < len(row) else ""
            cell = table.cell(i, j)
            cell.text = text
            for p in cell.text_frame.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(14 if n_rows <= 6 else max(9, 14 - (n_rows - 6) // 3))
                p.alignment = PP_ALIGN.CENTER
    return shape


# ---------- Chart ----------
CHART_KIND_MAP = {
    'bar': XL_CHART_TYPE.BAR_CLUSTERED,
    'line': XL_CHART_TYPE.LINE,
    'pie': XL_CHART_TYPE.PIE,
    'col': XL_CHART_TYPE.COLUMN_CLUSTERED,
}


def add_chart(slide, chart_info, prs):
    kind = chart_info.get('kind', 'bar').lower()
    raw = chart_info.get('data', '')
    categories, values = [], []
    for line in raw.splitlines():
        line = line.strip()
        if not line or ':' not in line:
            continue
        label, val = line.split(':', 1)
        try:
            values.append(float(val.strip().replace(',', '.')))
            categories.append(label.strip())
        except ValueError:
            continue
    if not values:
        return

    cd = CategoryChartData()
    cd.categories = categories
    cd.add_series('Значение', values)

    x = Cm(2)
    y = Cm(4)
    cx = prs.slide_width - Cm(4)
    cy = Cm(12)
    return slide.shapes.add_chart(
        CHART_KIND_MAP.get(kind, XL_CHART_TYPE.BAR_CLUSTERED),
        x, y, cx, cy, cd,
    )


# ---------- Utils ----------
def make_unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    ts = datetime.now().strftime("_%H%M%S")
    new_path = f"{base}{ts}{ext}"
    counter = 1
    while os.path.exists(new_path):
        new_path = f"{base}{ts}_{counter}{ext}"
        counter += 1
    return new_path

# ============================================================
# КЛОНИРОВАНИЕ СЛАЙДОВ (для режима «готовый шаблон»)
# ============================================================
import copy
from pptx.enum.shapes import PP_PLACEHOLDER


def strip_existing_slides(prs):
    """Удаляет все существующие слайды, сохраняя layouts и masters."""
    sldIdLst = prs.slides._sldIdLst
    for sldId in list(sldIdLst):
        try:
            prs.part.drop_rel(sldId.rId)
        except Exception:
            pass
        sldIdLst.remove(sldId)


def snapshot_slide(source_slide):
    """Снимает «слепок» слайда: layout + XML всех фигур (без удаления слайда)."""
    return {
        'layout': source_slide.slide_layout,
        'shapes': [copy.deepcopy(s.element) for s in source_slide.shapes],
    }


def restore_slide_from_snapshot(prs, snapshot):
    """Восстанавливает слайд из слепка: новый слайд + все фигуры из слепка."""
    new_slide = prs.slides.add_slide(snapshot['layout'])
    # Убираем placeholders, созданные add_slide (пустые)
    for shape in list(new_slide.shapes):
        if shape.is_placeholder:
            shape._element.getparent().remove(shape._element)
    # Возвращаем фигуры из слепка
    spTree = new_slide.shapes._spTree
    for el in snapshot['shapes']:
        spTree.append(copy.deepcopy(el))
    return new_slide


def fill_cloned_slide(slide, title=None, bullets=None, notes=None,
                      base_size=28, min_size=14):
    """Заполняет склонированный слайд текстом. Ищет placeholders, fallback на textboxes."""
    
    def _find_title_ph():
        for ph in slide.placeholders:
            try:
                ptype = ph.placeholder_format.type
            except Exception:
                continue
            if ptype in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE):
                return ph
        return None
    
    def _find_body_ph():
        for ph in slide.placeholders:
            try:
                ptype = ph.placeholder_format.type
            except Exception:
                continue
            if ptype in (PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT,
                         PP_PLACEHOLDER.SUBTITLE):
                return ph
        return None
    
    def _all_text_shapes():
        return [s for s in slide.shapes
                if s.has_text_frame and s.text_frame.text.strip()]
    
    # ---- Заголовок ----
    if title:
        target = _find_title_ph()
        if target is None:
            # Fallback: самый верхний текстовый блок
            candidates = _all_text_shapes()
            if candidates:
                candidates.sort(key=lambda s: (s.top if s.top is not None else 0))
                target = candidates[0]
        if target is not None:
            try:
                tf = target.text_frame
                if tf.paragraphs and tf.paragraphs[0].runs:
                    tf.paragraphs[0].runs[0].text = title
                    for extra in tf.paragraphs[0].runs[1:]:
                        extra.text = ""
                else:
                    tf.text = title
            except Exception:
                pass
    
    # ---- Список ----
    if bullets:
        target = _find_body_ph()
        if target is None:
            candidates = _all_text_shapes()
            if title:
                candidates = [c for c in candidates
                              if c.text_frame.text.strip() != title]
            if candidates:
                # Самый крупный блок по площади
                candidates.sort(
                    key=lambda s: (s.width or 0) * (s.height or 0),
                    reverse=True,
                )
                target = candidates[0]
        if target is not None:
            try:
                tf = target.text_frame
                tf.clear()
                tf.word_wrap = True
                total_chars = sum(len(t) for _, t in bullets)
                size = base_size
                if len(bullets) > 6 or total_chars > 400:
                    size = max(min_size, size - 4)
                if len(bullets) > 9 or total_chars > 700:
                    size = max(min_size, size - 4)
                for i, (lvl, txt) in enumerate(bullets):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    p.text = txt
                    p.level = min(int(lvl), 4)
                    for run in p.runs:
                        run.font.size = Pt(max(min_size, size - 4 * lvl))
            except Exception:
                pass
    
    # ---- Заметки ----
    if notes:
        try:
            slide.notes_slide.notes_text_frame.text = notes
        except Exception:
            pass

