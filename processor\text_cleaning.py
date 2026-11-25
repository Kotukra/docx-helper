# processor/text_cleaning.py
import re
from typing import List, Tuple
from logger import get_debug_logger

def remove_hidden_chars(text: str) -> str:
    invisible = re.compile(r'[\ufeff\u200b\u200c\u200d\u200e\u200f]')
    return invisible.sub('', text)

def replace_quotes(text: str) -> str:
    text = re.sub(r'(^|[ (\[{<])"', r'\1«', text)
    text = re.sub(r'"', '»', text)
    text = re.sub(r'(^|[ (\[{<])\'', r'\1‘', text)
    text = re.sub(r'\'', '’', text)
    return text

def replace_dashes(text: str) -> str:
    text = re.sub(r' -- ', ' — ', text)
    text = re.sub(r'—+', '—', text)
    return text

def remove_markdown(text: str) -> str:
    """Удаляет Markdown-разметку: жирный, курсив, экранирование."""
    text = re.sub(r'\\\*', '*', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    return text

def enhanced_clean_text(text: str, typography: bool = True, debug: bool = False) -> str:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"enhanced_clean_text: исходная длина {len(text)}")
    # Удаление HTML-тегов
    text = re.sub(r'<[^>]+>', '', text)
    # Удаление невидимых символов
    text = remove_hidden_chars(text)
    # Удаление управляющих символов (ASCII 0-31, кроме \n, \r, \t)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Удаление Markdown-разметки
    text = remove_markdown(text)
    # Сокращение множественных переносов
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Сокращение множественных пробелов
    text = re.sub(r' {2,}', ' ', text)
    # Пробелы перед знаками препинания
    text = re.sub(r'\s+([.,:;!?])', r'\1', text)
    # Пробелы вокруг скобок
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    # Удаление пустых строк в начале и конце
    lines = [line.strip() for line in text.split('\n')]
    while lines and lines[0] == '':
        lines.pop(0)
    while lines and lines[-1] == '':
        lines.pop()
    text = '\n'.join(lines)
    if typography:
        text = replace_quotes(text)
        text = replace_dashes(text)
    if debug:
        debug_logger.debug(f"enhanced_clean_text: длина после очистки {len(text)}")
    return text

def clean_text(text: str) -> str:
    text = re.sub(r'[*#]', '', text)
    text = re.sub(r'\n{2,}', '\n', text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\s+([.,:;!?])', r'\1', text)
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)

def detect_non_russian_words(text: str) -> List[str]:
    words = re.findall(r'\b[а-яёa-z]+(?:[-’][а-яёa-z]+)?\b', text, re.IGNORECASE)
    return [w for w in words if not re.search(r'[а-яё]', w, re.IGNORECASE)]

def find_extra_spaces(text: str) -> List[Tuple[str, str]]:
    problems = []
    for m in re.finditer(r' {2,}', text):
        problems.append(("множественные пробелы", m.group()))
    for m in re.finditer(r'\s+([.,:;!?])', text):
        problems.append(("пробел перед знаком", m.group()))
    for m in re.finditer(r'\(\s+', text):
        problems.append(("пробел после (", m.group()))
    for m in re.finditer(r'\s+\)', text):
        problems.append(("пробел перед )", m.group()))
    for m in re.finditer(r'^\s+', text, re.MULTILINE):
        problems.append(("пробел в начале строки", m.group()))
    for m in re.finditer(r'\s+$', text, re.MULTILINE):
        problems.append(("пробел в конце строки", m.group()))
    return problems

def find_extra_enters(text: str) -> List[Tuple[int, str]]:
    return [(m.start(), m.group()) for m in re.finditer(r'\n{2,}', text)]

def clean_markdown_source(text: str, typography: bool = False) -> str:
    """Мягкая очистка Markdown: сохраняет синтаксис, пустые строки и маркеры.

    Используется перед Markdown-парсером; не удаляет #, *, обратные кавычки,
    fenced code blocks, HTML-код и пользовательские маркеры [^...] / [IMAGE:...].
    """
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = remove_hidden_chars(text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Схлопываем только чрезмерные пустые строки, сохраняя разделение блоков.
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    # Убираем пробелы в конце строк, но не трогаем отступы внутри кода.
    text = re.sub(r'[ \t]+(?=\n)', '', text)
    text = text.strip('\n')
    if typography:
        # Типографику применяем только вне fenced code blocks.
        chunks = re.split(r'(^```[^\n]*\n.*?^```[ \t]*$)', text, flags=re.M | re.S)
        for i in range(0, len(chunks), 2):
            chunks[i] = replace_quotes(replace_dashes(chunks[i]))
        text = ''.join(chunks)
    return text


def clean_text_preserve_markup(text: str, typography: bool = True) -> str:
    """Безопасная очистка для Markdown: не удаляет разметку и пустые строки."""
    text = remove_hidden_chars(text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Сохраняем fenced code, Markdown-заголовки, таблицы и [^сноски].
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    if typography:
        # Типографика применяется только вне fenced code, чтобы не менять исходники.
        parts = re.split(r'(^```.*?$.*?^```\s*$)', text, flags=re.MULTILINE | re.DOTALL)
        for i in range(0, len(parts), 2):
            parts[i] = replace_dashes(replace_quotes(parts[i]))
        text = ''.join(parts)
    return text.strip('\n')
