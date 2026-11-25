# processor/doc_creator.py
import os
import re
import gc
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING

# Импортируем наш новый модуль
from .gost_builder import (
    setup_gost_styles, 
    insert_image_placeholder, 
    add_gost_table, 
    add_table_of_contents
)
from .footnotes import FootnoteManager, add_text_with_footnotes
from caption_numbering import CaptionNumberer
from markdown_editors import parse_image_marker_options
from .page_numbers import add_page_numbers
from .text_cleaning import enhanced_clean_text, clean_text, clean_markdown_source, find_extra_spaces, find_extra_enters, detect_non_russian_words
from .keywords import generate_filename_adaptive, generate_custom_filename, sanitize_filename
from .file_io import load_settings
from logger import logger, get_debug_logger
from document_profile_manager import resolve_profile_settings

# ---------- Вспомогательные функции ----------
def copy_doc_content(source: Document, target: Document) -> None:
    for para in source.paragraphs:
        new_p = target.add_paragraph()
        for run in para.runs:
            new_run = new_p.add_run(run.text)
            new_run.bold, new_run.italic, new_run.underline = run.bold, run.italic, run.underline
            new_run.font.name, new_run.font.size = run.font.name, run.font.size
        new_p.alignment = para.alignment
    for table in source.tables:
        new_tab = target.add_table(rows=len(table.rows), cols=len(table.columns))
        new_tab.style = table.style
        for i, row in enumerate(table.rows):
            for j, cell in enumerate(row.cells):
                new_tab.cell(i, j).text = cell.text

def load_title_by_key(settings: Dict, key: str) -> Optional[Document]:
    title_conf = settings.get('title_page')
    if not title_conf or not title_conf.get('enabled'):
        return None
    path = title_conf.get('templates', {}).get(key) or title_conf.get('templates', {}).get('default')
    if not path or not os.path.exists(path):
        return None
    return Document(path)

def get_title_for_part(settings: Dict, part_index: int) -> Optional[Document]:
    conf = settings.get('title_page', {})
    if not conf.get('enabled'):
        return None
    per = conf.get('per_part')
    if per is None:
        return load_title_by_key(settings, conf.get('selected_template', 'default'))
    if isinstance(per, str):
        return load_title_by_key(settings, per)
    if isinstance(per, list):
        idx = (part_index - 1) % len(per)
        return load_title_by_key(settings, per[idx])
    return load_title_by_key(settings, conf.get('selected_template', 'default'))

def is_table(lines: List[str], start: int) -> Tuple[bool, int, List[List[str]]]:
    """Улучшенное распознавание таблицы в формате Markdown."""
    if start >= len(lines):
        return False, 0, []
    while start < len(lines) and lines[start].strip() == '':
        start += 1
    if start >= len(lines):
        return False, 0, []

    table_lines = []
    idx = start
    while idx < len(lines):
        line = lines[idx].strip()
        if not line or '|' not in line:
            break
        table_lines.append(line)
        idx += 1

    if len(table_lines) < 2:
        return False, 0, []

    sep_idx = -1
    for i, line in enumerate(table_lines):
        if re.match(r'^[\|\s\-:]+$', line):
            sep_idx = i
            break

    if sep_idx == -1:
        return False, 0, []

    if sep_idx == 0:
        header, data_start = None, 1
    elif sep_idx == 1:
        header, data_start = table_lines[0], 2
    else:
        header, data_start = table_lines[0], 1

    def split_row(row: str) -> List[str]:
        if not row.startswith('|'): row = '|' + row
        if not row.endswith('|'): row = row + '|'
        inner = row[1:-1]
        cells, buf, escaped = [], [], False
        for char in inner:
            if escaped:
                buf.append(char); escaped = False
            elif char == '\\':
                escaped = True
            elif char == '|':
                cells.append(''.join(buf).strip()); buf = []
            else:
                buf.append(char)
        if escaped: buf.append('\\')
        cells.append(''.join(buf).strip())
        return cells

    max_cols = 0
    if header: max_cols = len(split_row(header))
    for i in range(data_start, len(table_lines)):
        if re.match(r'^[\|\s\-:]+$', table_lines[i]): continue
        max_cols = max(max_cols, len(split_row(table_lines[i])))

    if max_cols == 0:
        return False, 0, []

    result = []
    if header:
        cells = split_row(header)
        cells += [''] * (max_cols - len(cells))
        result.append(cells[:max_cols])

    for i in range(data_start, len(table_lines)):
        if re.match(r'^[\|\s\-:]+$', table_lines[i]): continue
        cells = split_row(table_lines[i])
        cells += [''] * (max_cols - len(cells))
        result.append(cells[:max_cols])

    if len(result) < 2:
        return False, 0, []

    return True, idx - start, result

def _make_unique_filename(filepath: str) -> str:
    if not os.path.exists(filepath):
        return filepath
    base, ext = os.path.splitext(filepath)
    timestamp = datetime.now().strftime("_%H%M%S")
    new_path = f"{base}{timestamp}{ext}"
    counter = 1
    while os.path.exists(new_path):
        new_path = f"{base}{timestamp}_{counter}{ext}"
        counter += 1
    return new_path

# ---------- Основная функция создания документа ----------
def create_word_document(
    text: str,
    output_path: str,
    settings: Optional[Dict] = None,
    settings_path: Optional[str] = None,
    title_doc: Optional[Document] = None,
    markdown_mode: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> str:
    if settings_path:
        settings = load_settings(settings_path)
    elif settings is None:
        settings = {}

    settings = resolve_profile_settings(settings)
    debug_mode = settings.get('debug_mode', False)
    if debug_mode:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"=== create_word_document (GOST): начало ===")
        debug_logger.debug(f"Выходной файл: {output_path}")
        debug_logger.debug(f"Длина текста: {len(text)}")

    logger.info(f"create_word_document: начало, выходной файл {output_path}, длина текста {len(text)}")

    # Извлекаем настройки (безопасно)
    def safe_float(val, default=0.0):
        try: return float(val) if val is not None else default
        except: return default

    page_width = Cm(safe_float(settings.get('page_width'), 21.0))
    page_height = Cm(safe_float(settings.get('page_height'), 29.7))
    
    margins = settings.get('margins', {})
    top = Cm(safe_float(margins.get('top', 2.0)))
    bottom = Cm(safe_float(margins.get('bottom', 2.0)))
    left = Cm(safe_float(margins.get('left', 3.0)))
    right = Cm(safe_float(margins.get('right', 1.5)))

    detect_issues = settings.get('detect_issues', True)

    # В Markdown-режиме нельзя применять обычную очистку: она удаляет #, *,
    # пустые строки и тем самым разрушает структуру исходной разметки.
    if markdown_mode:
        cleaned = clean_markdown_source(
            text, typography=bool(settings.get('enhanced_cleaning', False))
        )
    elif settings.get('enhanced_cleaning', False):
        cleaned = enhanced_clean_text(text, typography=True)
    else:
        cleaned = clean_text(text)
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
    logger.info("2. Текст очищен")

    try:
        # 1. Если передан титульный шаблон, продолжаем работу в его документе.
        # Это сохраняет таблицы, изображения, колонтитулы, стили и форматирование
        # титульного листа; копирование отдельных абзацев теряло эти элементы.
        doc = title_doc if title_doc is not None else Document()
        setup_gost_styles(doc, settings.get("_document_style_profile", {}))

        # Применяем геометрию профиля ко всем секциям документа, включая секции
        # уже существовавшего титульного шаблона.
        for section in doc.sections:
            section.page_width = page_width
            section.page_height = page_height
            section.top_margin = top
            section.bottom_margin = bottom
            section.left_margin = left
            section.right_margin = right
        logger.info("3. Стили и поля страницы установлены")

        fnmgr = FootnoteManager(doc) if settings.get('footnotes_enabled', True) else None 
        caption_numberer = CaptionNumberer(settings.get('auto_number_captions', True))

        # 2. Титульный лист уже находится в doc, так как использован сам шаблон.
        if title_doc is not None:
            doc.add_page_break()

        # 3. Содержание. Учитываем как явный маркер [TOC], так и
        # переключатель интерфейса gost_toc. Маркер имеет приоритет и
        # позволяет запросить оглавление даже при выключенном переключателе.
        has_toc_marker = bool(re.match(r'^\s*\[TOC\]\s*$', cleaned.splitlines()[0] if cleaned.splitlines() else '', re.I))
        if has_toc_marker:
            cleaned = re.sub(r'^\s*\[TOC\]\s*\n?', '', cleaned, count=1, flags=re.I)
        if has_toc_marker or bool(settings.get('gost_toc', False)):
            add_table_of_contents(doc)
            logger.info("4. Добавлено автособираемое оглавление")

        # 4. Парсинг текста
        if markdown_mode:
            from .markdown_utils import markdown_to_docx
            markdown_to_docx(
                cleaned, doc,
                settings.get('font_name', 'Times New Roman'),
                Pt(safe_float(settings.get('font_size'), 14)),
                {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER, "right": WD_ALIGN_PARAGRAPH.RIGHT, "justify": WD_ALIGN_PARAGRAPH.JUSTIFY}.get(settings.get("alignment", "justify"), WD_ALIGN_PARAGRAPH.JUSTIFY), Cm(safe_float(settings.get('first_line_indent'), 1.25)),
                Cm(safe_float(settings.get('left_indent'), 0)),
                Cm(safe_float(settings.get('right_indent'), 0)),
                fnmgr=fnmgr, settings=settings, base_dir=os.path.dirname(os.path.abspath(output_path)),
                caption_numberer=caption_numberer,
            )
        else:
            lines = cleaned.split('\n')
            idx = 0
            total = len(lines)
            
            while idx < total:
                if cancel_check and cancel_check():
                    raise InterruptedError("Отменено")

                line = lines[idx].strip()
                if not line:
                    idx += 1
                    continue

                appendix_marker = re.match(r'^\[APPENDIX:\s*(.*?)\s*\]$', line, re.I)
                if appendix_marker:
                    title = caption_numberer.format('appendix', appendix_marker.group(1).strip())
                    paragraph = doc.add_paragraph(title, style='Heading 1')
                    paragraph.paragraph_format.page_break_before = True
                    idx += 1
                    continue

                table_marker = re.match(r'^\[TABLE:\s*(.*?)\s*\]$', line, re.I)
                if table_marker:
                    table_start = idx + 1
                    while table_start < total and not lines[table_start].strip():
                        table_start += 1
                    is_marked_table, processed, tbl_data = is_table(lines, table_start)
                    if is_marked_table:
                        caption = caption_numberer.format('table', table_marker.group(1).strip())
                        add_gost_table(doc, tbl_data, caption=caption)
                        idx = table_start + processed
                        continue

                image_match = re.match(r'^\[IMAGE:\s*(.*?)\]$', line, re.IGNORECASE)
                if image_match:
                    payload = image_match.group(1).strip()
                    if ' | ' in payload:
                        image_path, caption, image_width, alignment = parse_image_marker_options(line)
                        width_cm = image_width or safe_float(settings.get('gost_img_width', 15.0), 15.0)
                        caption = caption_numberer.format('figure', caption)
                        from .markdown_utils import _add_image
                        _add_image(doc, image_path.strip(), caption,
                                   os.path.dirname(os.path.abspath(output_path)), width_cm, alignment)
                    else:
                        caption = caption_numberer.format('figure', payload)
                        insert_image_placeholder(doc, caption, width_cm=width_cm)
                    idx += 1
                    continue

                # --- Проверка на таблицу ---
                is_tbl, processed, tbl_data = is_table(lines, idx)
                if is_tbl:
                    add_gost_table(doc, tbl_data, caption=None)
                    idx += processed
                    continue

                # --- Проверка на Заголовок 1 ---
                if re.match(r'^(ВВЕДЕНИЕ|ЗАКЛЮЧЕНИЕ|СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ|ГЛАВА\s+\d+)', line.upper()):
                    doc.add_paragraph(line, style='Heading 1')
                    idx += 1
                    continue

                # --- Проверка на Заголовок 2 ---
                if re.match(r'^\d+\.\d+\s+[А-ЯA-Z]', line):
                    doc.add_paragraph(line, style='Heading 2')
                    idx += 1
                    continue

                # --- Обработка обычного текста со сносками ---
                               # --- Обработка обычного текста со сносками ---
                if '[^' in line and fnmgr is not None:
                    p = doc.add_paragraph(style='Normal')
                    add_text_with_footnotes(p, line, fnmgr)
                else:
                    doc.add_paragraph(line, style='Normal')

                idx += 1
                if progress_callback and idx % 50 == 0:
                    progress_callback(idx, total, "Обработка...")

              # 5. Сноски и нумерация страниц
        if fnmgr is not None:
            fnmgr.finalize()

        if settings.get('page_numbers', True):
            align_map = {
                "left":   WD_ALIGN_PARAGRAPH.LEFT,
                "center": WD_ALIGN_PARAGRAPH.CENTER,
                "right":  WD_ALIGN_PARAGRAPH.RIGHT,
            }
            add_page_numbers(
                doc,
                align=align_map.get(settings.get('page_numbers_align', 'center'),
                                    WD_ALIGN_PARAGRAPH.CENTER),
                start_at=int(settings.get('page_numbers_start', 1)),
                skip_first_page=bool(settings.get('page_numbers_skip_first', True)),
                position=settings.get('page_numbers_position', 'footer'),
            )

        # 6. Сохранение
        final_path = _make_unique_filename(output_path)
        doc.save(final_path)
        logger.info(f"Документ сохранён: {final_path}")

        del doc

        if detect_issues:
            print("=== ОТЧЁТ О ПРОБЛЕМАХ ===")
            for typ, frag in find_extra_spaces(text):
                print(f"Пробелы: {typ} -> '{frag}'")
            print("=== КОНЕЦ ОТЧЁТА ===")

        return final_path

    except InterruptedError:
        logger.warning("Создание документа прервано пользователем")
        raise
    except Exception as e:
        logger.exception(f"Ошибка при создании документа {output_path}")
        raise

# ---------- Пакетная обработка (осталась без изменений) ----------
class ProgressReporter:
    def __init__(self, callback: Optional[Callable[[int, int, str], None]] = None,
                 cancel_check: Optional[Callable[[], bool]] = None):
        self.callback = callback
        self.cancel_check = cancel_check
    def update(self, current: int, total: int, message: str = ""):
        if self.callback:
            self.callback(current, total, message)
    def is_cancelled(self) -> bool:
        return self.cancel_check is not None and self.cancel_check()

def batch_process_documents(
    text_parts: List[str],
    settings: Dict,
    output_folder: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> Tuple[List[str], bool]:
    reporter = ProgressReporter(progress_callback, cancel_check)
    top_n = settings.get("naming_top_n", 4)
    markdown_mode = settings.get('markdown_mode', False)
    created_files = []
    total = len(text_parts)
    for idx, part_text in enumerate(text_parts, start=1):
        if reporter.is_cancelled():
            return created_files, True
        reporter.update(idx, total, f"Часть {idx}/{total}")
        name_template = settings.get('filename_template', '{keywords}')
        keywords = generate_filename_adaptive(part_text, top_n=top_n)
        if not keywords or keywords == "output":
            keywords = "output"
        base_name = generate_custom_filename(name_template, keywords, idx)
        base_name = sanitize_filename(base_name)
        filename = f"{base_name}_part{idx}.docx" if total > 1 else f"{base_name}.docx"
        full_path = os.path.join(output_folder, filename)
        title_doc = None
        if settings.get("title_enabled", False):
            title_doc = get_title_for_part(settings, idx)
        create_word_document(
            part_text, full_path, settings=settings, title_doc=title_doc,
            markdown_mode=markdown_mode, progress_callback=None, cancel_check=reporter.is_cancelled
        )
        created_files.append(full_path)
    return created_files, False
