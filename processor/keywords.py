# processor/keywords.py
import re
from collections import Counter
from datetime import datetime
from typing import Optional
from typing import List, Optional
from .availability import YAKE_AVAILABLE, LANGDETECT_AVAILABLE
from .constants import STOP_WORDS
from logger import get_debug_logger

def detect_language(text: str, debug: bool = False) -> str:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug("detect_language: начало")
    if not LANGDETECT_AVAILABLE:
        if debug:
            debug_logger.debug("langdetect недоступен, возвращаем 'ru'")
        return 'ru'
    try:
        from langdetect import detect, LangDetectException
        sample = text[:500].replace('\n', ' ')
        lang = detect(sample)
        if debug:
            debug_logger.debug(f"Определён язык: {lang}")
        return lang
    except Exception as e:
        if debug:
            debug_logger.debug(f"Ошибка определения языка: {e}, возвращаем 'ru'")
        return 'ru'

def generate_filename_adaptive(text: str, top_n: int = 4, debug: bool = False) -> str:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"generate_filename_adaptive: top_n={top_n}, длина текста {len(text)}")
    if not YAKE_AVAILABLE:
        if debug:
            debug_logger.debug("YAKE недоступен, используем комбинированный метод")
        return generate_filename_combined(text, top_n, debug)
    lang = detect_language(text, debug)
    yake_lang = 'ru' if lang.startswith('ru') else 'en'
    try:
        import yake
        kw_extractor = yake.KeywordExtractor(lan=yake_lang, top=top_n, n=1)
        keywords = kw_extractor.extract_keywords(text)
        words = [kw[0] for kw in keywords]
        if debug:
            debug_logger.debug(f"YAKE извлёк: {words}")
        if words:
            clean_words = [re.sub(r'[^а-яёa-z]', '', w.lower()) for w in words]
            clean_words = [w for w in clean_words if w and w not in STOP_WORDS]
            if clean_words:
                result = '_'.join(clean_words[:top_n])
                if debug:
                    debug_logger.debug(f"Результат YAKE: {result}")
                return result
    except Exception as e:
        if debug:
            debug_logger.debug(f"Ошибка YAKE: {e}, переходим к комбинированному")
    return generate_filename_combined(text, top_n, debug)

def generate_filename_combined(text: str, top_n: int = 4, debug: bool = False) -> str:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug("generate_filename_combined: начало")
    clean = re.sub(r'[*#]', '', text)
    clean = re.sub(r'\s+', ' ', clean)
    if YAKE_AVAILABLE:
        try:
            import yake
            kw_extractor = yake.KeywordExtractor(lan="ru", top=top_n, n=1)
            keywords = kw_extractor.extract_keywords(clean)
            words = [kw[0] for kw in keywords]
            if debug:
                debug_logger.debug(f"YAKE (комб) извлёк: {words}")
            if words:
                clean_words = [re.sub(r'[^а-яёa-z]', '', w.lower()) for w in words]
                clean_words = [w for w in clean_words if w and w not in STOP_WORDS]
                if clean_words:
                    result = '_'.join(clean_words[:top_n])
                    if debug:
                        debug_logger.debug(f"Результат комб (YAKE): {result}")
                    return result
        except Exception as e:
            if debug:
                debug_logger.debug(f"Ошибка YAKE в комб: {e}")
    words_all = re.findall(r'\b[а-яёa-z]+\b', clean.lower())
    filtered = [w for w in words_all if w not in STOP_WORDS]
    if debug:
        debug_logger.debug(f"Всего слов после фильтрации: {len(filtered)}")
    if not filtered:
        if debug:
            debug_logger.debug("Нет слов, возвращаем 'output'")
        return "output"
    counter = Counter(filtered)
    result = '_'.join([w for w, _ in counter.most_common(top_n)])
    if debug:
        debug_logger.debug(f"Результат комб (счётчик): {result}")
    return result

def sanitize_filename(name: str, max_len: int = 50, debug: bool = False) -> str:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"sanitize_filename: исходное '{name}'")
    name = re.sub(r'[\\/*?:"<>|]', '_', name)
    if len(name) > max_len:
        name = name[:max_len]
    result = name.strip()
    if debug:
        debug_logger.debug(f"sanitize_filename: результат '{result}'")
    return result

def generate_custom_filename(template: str, keywords: str, part_num: int = None, debug: bool = False) -> str:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"generate_custom_filename: template='{template}', keywords='{keywords}', part={part_num}")
    now = datetime.now()
    replacements = {
        '{keywords}': keywords,
        '{date}': now.strftime('%Y-%m-%d'),
        '{time}': now.strftime('%H%M%S'),
        '{part}': str(part_num) if part_num is not None else ''
    }
    for k, v in replacements.items():
        template = template.replace(k, v)
    template = re.sub(r'[\\/*?:"<>|]', '_', template)
    template = re.sub(r'_+', '_', template)
    result = template.strip('_')
    if debug:
        debug_logger.debug(f"generate_custom_filename: результат '{result}'")
    return result

def split_text_by_marker(text: str, marker: str, debug: bool = False,
                         enabled: bool = True) -> List[str]:
    if not enabled:
        return [text]
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"split_text_by_marker: marker='{marker}'")
    import re
    parts = re.split(r'\n\s*' + re.escape(marker) + r'\s*\n', text)
    result = [p.strip() for p in parts if p.strip()] or [text]
    if debug:
        debug_logger.debug(f"split_text_by_marker: найдено {len(result)} частей")
    return result
