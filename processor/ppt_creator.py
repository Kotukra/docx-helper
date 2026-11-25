# processor/ppt_creator.py
import os
import re
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE_TYPE
from markdown_editors import parse_image_marker_options
from slide_editor import parse_slide_positions, normalize_slide_positions
from logger import logger
from .ppt_builder import (
    find_layout_by_name, set_title, try_set_subtitle, find_body_placeholder,
    add_bullets_auto, add_image_or_placeholder, add_full_image,
    add_table, add_chart, make_unique_path,
    strip_existing_slides, snapshot_slide, restore_slide_from_snapshot, fill_cloned_slide,
)


SLIDE_SPLIT_RE = re.compile(r'\n\s*---\s*\n')


def add_slide_numbers(prs, color="666666"):
    """Add unobtrusive static slide numbers within the bottom-right slide bounds."""
    from pptx.dml.color import RGBColor
    try:
        rgb = RGBColor.from_string(str(color).lstrip("#"))
    except (ValueError, TypeError):
        rgb = RGBColor(102, 102, 102)
    x = max(0, prs.slide_width - Inches(0.72))
    y = max(0, prs.slide_height - Inches(0.38))
    width = min(Inches(0.52), prs.slide_width - x)
    height = min(Inches(0.24), prs.slide_height - y)
    for index, slide in enumerate(prs.slides, start=1):
        shape = slide.shapes.add_textbox(x, y, width, height)
        non_visual = shape._element.xpath(".//p:cNvPr")
        if non_visual:
            non_visual[0].set("name", "GOST slide number")
        frame = shape.text_frame
        frame.clear()
        frame.margin_left = frame.margin_right = 0
        frame.margin_top = frame.margin_bottom = 0
        paragraph = frame.paragraphs[0]
        paragraph.alignment = PP_ALIGN.RIGHT
        run = paragraph.add_run()
        run.text = str(index)
        run.font.size = Pt(9)
        run.font.color.rgb = rgb


def parse_presentation(markup: str):
    """Разбирает разметку на список слайдов."""
    blocks = SLIDE_SPLIT_RE.split(markup.strip())
    slides = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        m = re.match(r'^\[SLIDE:\s*(\w+)\]', block)
        if m:
            stype = m.group(1).lower()
            content = block[m.end():].lstrip('\n')
        else:
            stype = 'bullets'
            content = block

        title_m = re.search(r'^#\s*(.+)$', content, re.MULTILINE)
        title = title_m.group(1).strip() if title_m else ''
        content_wo_title = re.sub(r'^#\s*.+\n?', '', content, count=1, flags=re.MULTILINE)

        sub_m = re.search(r'\[SUB:\s*(.+?)\]', content_wo_title)
        subtitle = sub_m.group(1).strip() if sub_m else ''

        bullets = []
        for line in content_wo_title.splitlines():
            bm = re.match(r'^(\s*)-\s+(.+)$', line)
            if bm:
                level = len(bm.group(1)) // 2
                bullets.append((level, bm.group(2).strip()))

        notes_m = re.search(r'\[NOTES:\s*(.+?)\]', content_wo_title, re.DOTALL)
        notes = notes_m.group(1).strip() if notes_m else ''

        images = []
        for image_payload in re.findall(r'\[IMAGE:\s*(.+?)\]', content_wo_title):
            parsed_image = parse_image_marker_options(f"[IMAGE: {image_payload}]")
            if parsed_image:
                images.append(parsed_image[0] or parsed_image[1])

        chart = None
        cm = re.search(r'\[CHART:\s*(\w+)\]\s*(.+?)\s*\[/CHART\]', content_wo_title, re.DOTALL)
        if cm:
            chart = {'kind': cm.group(1).lower(), 'data': cm.group(2).strip()}

        table = None
        tm = re.search(r'\[TABLE\]\s*(.+?)\s*\[/TABLE\]', content_wo_title, re.DOTALL)
        if tm:
            rows = []
            for line in tm.group(1).strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                if set(line) <= set('|-: '):
                    continue
                if line.startswith('|'):
                    line = line[1:]
                if line.endswith('|'):
                    line = line[:-1]
                cells = [c.strip() for c in line.split('|')]
                rows.append(cells)
            if len(rows) >= 2:
                table = rows

        slides.append({
            'type': stype,
            'title': title,
            'subtitle': subtitle,
            'bullets': bullets,
            'notes': notes,
            'images': images,
            'chart': chart,
            'table': table,
            'positions': parse_slide_positions(content_wo_title),
        })
    return slides


def _apply_slide_positions(slide, slide_data, prs):
    positions = normalize_slide_positions(slide_data.get('positions', {}))
    if not positions:
        return

    targets = {}
    title_shape = slide.shapes.title
    title = slide_data.get('title', '').strip()
    if title_shape is None and title:
        title_shape = next((shape for shape in slide.shapes
                            if shape.has_text_frame and shape.text_frame.text.strip() == title), None)
    if title_shape is not None:
        targets['title'] = title_shape

    subtitle = slide_data.get('subtitle', '').strip()
    if subtitle:
        targets['subtitle'] = next((shape for shape in slide.shapes
                                    if shape.has_text_frame and shape.text_frame.text.strip() == subtitle
                                    and shape is not title_shape), None)

    body = find_body_placeholder(slide)
    if body is None:
        bullet_text = {text for _level, text in slide_data.get('bullets', [])}
        body = next((shape for shape in slide.shapes if shape.has_text_frame
                     and any(line.strip() in bullet_text for line in shape.text_frame.text.splitlines())), None)
    if body is not None:
        targets['body'] = body

    for shape in slide.shapes:
        if shape.name.startswith('GOST layout '):
            targets[shape.name[len('GOST layout '):]] = shape
        if getattr(shape, 'has_table', False) and shape.has_table:
            targets.setdefault('table', shape)
        if getattr(shape, 'has_chart', False) and shape.has_chart:
            targets.setdefault('chart', shape)
    pictures = [shape for shape in slide.shapes if shape.shape_type == MSO_SHAPE_TYPE.PICTURE]
    if pictures:
        targets.setdefault('image_1', pictures[0])

    slide_width, slide_height = prs.slide_width, prs.slide_height
    for key, box in positions.items():
        shape = targets.get(key)
        if shape is None:
            continue
        x, y, width, height = box
        left, top = round(x * slide_width), round(y * slide_height)
        shape_width, shape_height = round(width * slide_width), round(height * slide_height)
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            try:
                image_width, image_height = shape.image.size
                scale = min(shape_width / image_width, shape_height / image_height)
                shape_width = round(image_width * scale)
                shape_height = round(image_height * scale)
                left += (round(width * slide_width) - shape_width) // 2
                top += (round(height * slide_height) - shape_height) // 2
            except Exception:
                pass
        shape.left, shape.top = left, top
        shape.width, shape.height = shape_width, shape_height
        shape.name = f'GOST layout {key}'


def create_presentation(markup: str, output_path: str, template_path: str,
                        settings: dict) -> str:
    if not template_path or not os.path.exists(template_path):
        raise FileNotFoundError(f"Шаблон не найден: {template_path}")

    prs = Presentation(template_path)
    original_count = len(prs.slides)

    use_clone = bool(settings.get('ppt_use_clone_mode', False))
    clone_map = settings.get('ppt_clone_map', {}) or {}   # {type: 1-based slide #}

    # ---- 1. Снимаем слепки с образцов ДО удаления демо-слайдов ----
    snapshots = {}
    if use_clone:
        for stype, page_num in clone_map.items():
            try:
                page_num = int(page_num)
            except Exception:
                continue
            if 1 <= page_num <= original_count:
                snapshots[stype] = snapshot_slide(prs.slides[page_num - 1])
        logger.info(f"Режим клонирования: снято слепков — {len(snapshots)}")

    # ---- 2. Удаляем все демо-слайды шаблона ----
    strip_existing_slides(prs)

    # ---- 3. Парсим разметку ----
    slides_data = parse_presentation(markup)
    if not slides_data:
        raise ValueError("Не удалось разобрать ни одного слайда")

    layout_names = {
        'title':       settings.get('ppt_layout_title', 'Title Slide'),
        'bullets':     settings.get('ppt_layout_bullets', 'Title and Content'),
        'section':     settings.get('ppt_layout_section', 'Section Header'),
        'image':       settings.get('ppt_layout_image', 'Two Content'),
        'image_full':  settings.get('ppt_layout_image', 'Two Content'),
        'image_right': settings.get('ppt_layout_image', 'Two Content'),
        'image_left':  settings.get('ppt_layout_image', 'Two Content'),
        'table':       settings.get('ppt_layout_table', 'Title and Content'),
        'chart':       settings.get('ppt_layout_chart', 'Title and Content'),
        'conclusion':  settings.get('ppt_layout_conclusion', 'Title Slide'),
    }

    base_size = int(settings.get('ppt_bullet_size', 28))
    min_size = int(settings.get('ppt_bullet_min_size', 14))
    max_items = int(settings.get('ppt_max_items', 8))
    keep_notes = bool(settings.get('ppt_keep_notes', True))

    for sd in slides_data:
        stype = sd['type']

        # ---- Путь A: клонирование слайда-образца ----
        snapshot = snapshots.get(stype)
        if snapshot is not None:
            slide = restore_slide_from_snapshot(prs, snapshot)
            fill_cloned_slide(
                slide,
                title=sd['title'] or None,
                bullets=sd['bullets'] or None,
                notes=(sd['notes'] or None) if keep_notes else None,
                base_size=base_size,
                min_size=min_size,
            )
            # Спец-случаи для image/table/chart — дорисовываем ПОВЕРХ клона
            if stype in ('image_right', 'image_left', 'image'):
                side = 'left' if stype == 'image_left' else 'right'
                image_shape = add_image_or_placeholder(slide, sd['images'], prs, side=side)
                if image_shape is not None:
                    image_shape.name = 'GOST layout image_1'
            elif stype == 'image_full':
                image_shape = add_full_image(slide, sd['images'], prs)
                if image_shape is not None:
                    image_shape.name = 'GOST layout image_1'
            elif stype == 'table' and sd['table']:
                add_table(slide, sd['table'], prs)
            elif stype == 'chart' and sd['chart']:
                add_chart(slide, sd['chart'], prs)
            _apply_slide_positions(slide, sd, prs)
            continue

        # ---- Путь B: старый режим — по имени layout ----
        layout = find_layout_by_name(prs, layout_names.get(stype, 'Title and Content'))
        slide = prs.slides.add_slide(layout)

        set_title(slide, sd['title'], prs)

        if stype in ('title', 'conclusion'):
            if sd['subtitle']:
                try_set_subtitle(slide, sd['subtitle'])
            elif sd['bullets']:
                joined = ' | '.join(b for _, b in sd['bullets'])
                try_set_subtitle(slide, joined)
        elif stype == 'section':
            if sd['subtitle']:
                try_set_subtitle(slide, sd['subtitle'])
            elif sd['bullets']:
                try_set_subtitle(slide, ' '.join(b for _, b in sd['bullets']))
        elif stype == 'bullets':
            body = find_body_placeholder(slide)
            if body and sd['bullets']:
                if len(sd['bullets']) > max_items:
                    logger.warning(
                        f"Слайд «{sd['title']}»: {len(sd['bullets'])} пунктов "
                        f"превышает лимит {max_items}"
                    )
                add_bullets_auto(body, sd['bullets'], base_size, min_size)
        elif stype == 'image_full':
            body = find_body_placeholder(slide)
            if body is not None:
                try:
                    body._element.getparent().remove(body._element)
                except Exception:
                    pass
            image_shape = add_full_image(slide, sd['images'], prs)
            if image_shape is not None:
                image_shape.name = 'GOST layout image_1'
        elif stype in ('image_right', 'image_left', 'image'):
            side = 'left' if stype == 'image_left' else 'right'
            image_shape = add_image_or_placeholder(slide, sd['images'], prs, side=side)
            if image_shape is not None:
                image_shape.name = 'GOST layout image_1'
            body = find_body_placeholder(slide)
            if body and sd['bullets']:
                add_bullets_auto(body, sd['bullets'], base_size, min_size)
        elif stype == 'table' and sd['table']:
            body = find_body_placeholder(slide)
            if body is not None:
                try:
                    body._element.getparent().remove(body._element)
                except Exception:
                    pass
            add_table(slide, sd['table'], prs)
        elif stype == 'chart' and sd['chart']:
            body = find_body_placeholder(slide)
            if body is not None:
                try:
                    body._element.getparent().remove(body._element)
                except Exception:
                    pass
            add_chart(slide, sd['chart'], prs)
        else:
            body = find_body_placeholder(slide)
            if body and sd['bullets']:
                add_bullets_auto(body, sd['bullets'], base_size, min_size)

        if keep_notes and sd['notes']:
            try:
                slide.notes_slide.notes_text_frame.text = sd['notes']
            except Exception as e:
                logger.warning(f"Не удалось записать заметки: {e}")

        _apply_slide_positions(slide, sd, prs)

    if settings.get('ppt_slide_numbers', False):
        add_slide_numbers(prs, settings.get('ppt_slide_number_color', '666666'))

    final_path = make_unique_path(output_path)
    prs.save(final_path)
    logger.info(f"Презентация сохранена: {final_path}")
    return final_path

