# processor/file_io.py
import os
import json
import sys
import subprocess
from typing import Optional, Dict
from docx import Document

from .availability import MARKDOWN_AVAILABLE, DOCX2PDF_AVAILABLE
from .constants import REQUIRED_PACKAGES
from logger import get_debug_logger

# ---------- Чтение разных форматов ----------
def _iter_pptx_shapes(shapes):
    """Yield shapes recursively so text inside grouped PowerPoint objects is retained."""
    for shape in shapes:
        if getattr(shape, "shape_type", None) == 6 and hasattr(shape, "shapes"):
            yield from _iter_pptx_shapes(shape.shapes)
        else:
            yield shape


def extract_text_from_docx(filepath: str, debug: bool = False) -> str:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"extract_text_from_docx: {filepath}")
    doc = Document(filepath)
    text = '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
    if debug:
        debug_logger.debug(f"Извлечено {len(text)} символов")
    return text

def extract_text_from_pdf(filepath: str, debug: bool = False) -> str:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"extract_text_from_pdf: {filepath}")
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("Установите pdfplumber: pip install pdfplumber")
    text_pages = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_pages.append(text)
    result = '\n'.join(text_pages)
    if debug:
        debug_logger.debug(f"Извлечено {len(result)} символов")
    return result

def extract_text_from_html(filepath: str, debug: bool = False) -> str:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"extract_text_from_html: {filepath}")
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("Установите beautifulsoup4: pip install beautifulsoup4")
    with open(filepath, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    for script in soup(["script", "style"]):
        script.decompose()
    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    result = '\n'.join(chunk for line in lines for chunk in line.split("  ") if chunk)
    if debug:
        debug_logger.debug(f"Извлечено {len(result)} символов")
    return result

def extract_text_from_markdown(filepath: str, debug: bool = False) -> str:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"extract_text_from_markdown: {filepath}")
    if not MARKDOWN_AVAILABLE:
        raise ImportError("Установите markdown: pip install markdown")
    import markdown
    with open(filepath, 'r', encoding='utf-8') as f:
        html = markdown.markdown(f.read(), extensions=['extra'])
    import re
    result = re.sub(r'<[^>]+>', '', html)
    if debug:
        debug_logger.debug(f"Извлечено {len(result)} символов")
    return result

def extract_text_from_odt(filepath: str, debug: bool = False) -> str:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"extract_text_from_odt: {filepath}")
    try:
        from odf import text, teletype
        from odf.opendocument import load as load_odt
    except ImportError:
        raise ImportError("Установите odfpy: pip install odfpy")
    odt_doc = load_odt(filepath)
    all_texts = odt_doc.getElementsByType(text.P)
    result = '\n'.join(teletype.extractText(elem) for elem in all_texts)
    if debug:
        debug_logger.debug(f"Извлечено {len(result)} символов")
    return result

def extract_text_from_pptx(filepath: str, debug: bool = False) -> str:
    """Extract readable slide text and table rows from a PowerPoint file."""
    try:
        from pptx import Presentation
    except ImportError as exc:
        raise ImportError("Установите python-pptx: pip install python-pptx") from exc
    presentation = Presentation(filepath)
    slides = []
    for index, slide in enumerate(presentation.slides, start=1):
        lines = [f"Слайд {index}"]
        for shape in _iter_pptx_shapes(slide.shapes):
            if shape.is_placeholder and getattr(shape, "is_placeholder", False) and shape.shape_type == 13:
                continue
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    values = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    if any(values):
                        lines.append(" | ".join(values))
            elif getattr(shape, "has_text_frame", False):
                for paragraph in shape.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        lines.append(text)
            elif shape.shape_type == 13:
                lines.append("[Изображение на слайде]")
        slides.append("\n".join(lines))
    result = "\n\n".join(slides)
    if debug:
        get_debug_logger().debug(f"Извлечено {len(result)} символов из {len(presentation.slides)} слайдов")
    return result

def read_file_content(filepath: str, debug: bool = False) -> str:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"read_file_content: {filepath}")
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.txt':
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
            if debug:
                debug_logger.debug(f"Загружено {len(text)} символов из TXT")
            return text
    elif ext == '.docx':
        return extract_text_from_docx(filepath, debug)
    elif ext == '.pdf':
        return extract_text_from_pdf(filepath, debug)
    elif ext in ('.html', '.htm'):
        return extract_text_from_html(filepath, debug)
    elif ext == '.md':
        return extract_text_from_markdown(filepath, debug)
    elif ext == '.odt':
        return extract_text_from_odt(filepath, debug)
    elif ext == '.pptx':
        return extract_text_from_pptx(filepath, debug)
    else:
        raise ValueError(f"Неподдерживаемый формат: {ext}")

# ---------- Профили ----------
def save_profile(profile_path: str, settings: Dict, debug: bool = False) -> bool:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"save_profile: {profile_path}")
    try:
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        if debug:
            debug_logger.debug("Профиль сохранён")
        return True
    except Exception as e:
        if debug:
            debug_logger.exception(f"Ошибка сохранения профиля: {e}")
        print(f"Ошибка сохранения профиля: {e}")
        return False

def load_profile(profile_path: str, debug: bool = False) -> Optional[Dict]:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"load_profile: {profile_path}")
    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if debug:
            debug_logger.debug(f"Загружено {len(data)} ключей")
        return data
    except Exception as e:
        if debug:
            debug_logger.exception(f"Ошибка загрузки профиля: {e}")
        print(f"Ошибка загрузки профиля: {e}")
        return None

def load_settings(json_path: str, debug: bool = False) -> Dict:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"load_settings: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if debug:
        debug_logger.debug(f"Загружено {len(data)} ключей")
    return data

# ---------- Открытие файлов ----------
def open_file_with_default_app(filepath: str) -> bool:
    if not os.path.exists(filepath):
        return False
    try:
        if sys.platform == 'win32':
            os.startfile(filepath)
        elif sys.platform == 'darwin':
            subprocess.run(['open', filepath])
        else:
            subprocess.run(['xdg-open', filepath])
        return True
    except Exception:
        return False

# ---------- Экспорт PDF ----------
def export_to_pdf(docx_path: str, pdf_path: str = None, debug: bool = False) -> Optional[str]:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"export_to_pdf: {docx_path} -> {pdf_path}")
    if not os.path.exists(docx_path):
        if debug:
            debug_logger.error("DOCX не найден")
        return None
    if pdf_path is None:
        pdf_path = os.path.splitext(docx_path)[0] + '.pdf'
    if DOCX2PDF_AVAILABLE:
        try:
            from docx2pdf import convert
            convert(docx_path, pdf_path)
            if os.path.exists(pdf_path):
                if debug:
                    debug_logger.debug(f"PDF создан через docx2pdf: {pdf_path}")
                return pdf_path
        except Exception as e:
            if debug:
                debug_logger.exception(f"docx2pdf ошибка: {e}")
    # Fallback: LibreOffice
    try:
        soffice = None
        if sys.platform == 'win32':
            for p in [r'C:\Program Files\LibreOffice\program\soffice.exe',
                      r'C:\Program Files (x86)\LibreOffice\program\soffice.exe']:
                if os.path.exists(p):
                    soffice = p
                    break
        else:
            for cmd in ['libreoffice', 'soffice']:
                if subprocess.call(['which', cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                    soffice = cmd
                    break
        if soffice:
            if debug:
                debug_logger.debug(f"Используем LibreOffice: {soffice}")
            subprocess.run([soffice, '--headless', '--convert-to', 'pdf',
                            '--outdir', os.path.dirname(pdf_path), docx_path], check=True, timeout=60)
            generated = os.path.join(os.path.dirname(pdf_path), os.path.splitext(os.path.basename(docx_path))[0] + '.pdf')
            if generated != pdf_path and os.path.exists(generated):
                os.rename(generated, pdf_path)
            if os.path.exists(pdf_path):
                if debug:
                    debug_logger.debug(f"PDF создан через LibreOffice: {pdf_path}")
                return pdf_path
    except Exception as e:
        if debug:
            debug_logger.exception(f"LibreOffice ошибка: {e}")
    if debug:
        debug_logger.error("Не удалось конвертировать в PDF")
    print("Не удалось конвертировать в PDF. Установите docx2pdf или LibreOffice.")
    return None

# ---------- HTML-предпросмотр ----------
def docx_to_html(docx_path: str, html_path: str = None, debug: bool = False) -> Optional[str]:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"docx_to_html: {docx_path}")
    if not os.path.exists(docx_path):
        if debug:
            debug_logger.error("DOCX не найден")
        return None
    if html_path is None:
        html_path = os.path.splitext(docx_path)[0] + ".html"
    try:
        doc = Document(docx_path)
        html = ["<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Preview</title>"]
        html.append("<style>body { font-family: 'Times New Roman'; margin: 40px; }</style></head><body>")
        for para in doc.paragraphs:
            html.append("<p>")
            for run in para.runs:
                text = run.text
                if run.bold:
                    text = f"<b>{text}</b>"
                if run.italic:
                    text = f"<i>{text}</i>"
                if run.underline:
                    text = f"<u>{text}</u>"
                html.append(text)
            html.append("</p>")
        html.append("</body></html>")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(''.join(html))
        if debug:
            debug_logger.debug(f"HTML создан: {html_path}")
        return html_path
    except Exception as e:
        if debug:
            debug_logger.exception(f"Ошибка создания HTML: {e}")
        print(f"Ошибка создания HTML: {e}")
        return None
