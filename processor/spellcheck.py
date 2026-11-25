# processor/spellcheck.py
import subprocess
import re
from typing import List, Dict, Optional

from .availability import LANGUAGETOOL_AVAILABLE
from logger import get_debug_logger

_language_tool = None
_java_version_ok = None

def check_java_version(debug: bool = False):
    global _java_version_ok
    if _java_version_ok is not None:
        return _java_version_ok
    try:
        result = subprocess.run(['java', '-version'], capture_output=True, text=True)
        for line in result.stderr.split('\n'):
            if 'version' in line:
                match = re.search(r'\"?(\d+)\.', line)
                if match:
                    major = int(match.group(1))
                    _java_version_ok = (major >= 17)
                    if debug:
                        debug_logger = get_debug_logger()
                        debug_logger.debug(f"Java версия: {major}, {'OK' if _java_version_ok else 'не подходит'}")
                    if not _java_version_ok:
                        print(f"Предупреждение: Java {major} < 17. LanguageTool отключён.")
                    return _java_version_ok
        _java_version_ok = False
    except Exception as e:
        _java_version_ok = False
        if debug:
            debug_logger = get_debug_logger()
            debug_logger.debug(f"Java не найдена: {e}")
        print("Java не найдена. LanguageTool отключён.")
    return _java_version_ok

def get_language_tool(lang: str = 'ru', debug: bool = False):
    global _language_tool
    if not LANGUAGETOOL_AVAILABLE or not check_java_version(debug):
        if debug:
            debug_logger = get_debug_logger()
            debug_logger.debug("LanguageTool недоступен")
        return None
    lang_code = 'ru-RU' if lang.startswith('ru') else 'en-US'
    if _language_tool is None or _language_tool.lang != lang_code:
        try:
            import language_tool_python
            _language_tool = language_tool_python.LanguageTool(lang_code)
            if debug:
                debug_logger = get_debug_logger()
                debug_logger.debug(f"LanguageTool инициализирован для {lang_code}")
        except Exception as e:
            if debug:
                debug_logger = get_debug_logger()
                debug_logger.exception(f"LanguageTool init error: {e}")
            print(f"LanguageTool init error: {e}")
            return None
    return _language_tool

def check_spelling(text: str, lang: str = 'ru', debug: bool = False) -> List[Dict]:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"check_spelling: lang={lang}, длина текста {len(text)}")
    tool = get_language_tool(lang, debug)
    if not tool:
        return []
    try:
        matches = tool.check(text)
        result = [{'offset': m.offset, 'error': m.context[m.offset:m.offset+m.errorLength],
                   'message': m.message, 'suggestions': m.replacements[:5]} for m in matches]
        if debug:
            debug_logger.debug(f"Найдено ошибок: {len(result)}")
        return result
    except Exception as e:
        if debug:
            debug_logger.exception(f"Spell check error: {e}")
        print(f"Spell check error: {e}")
        return []

def correct_text_with_tool(text: str, lang: str = 'ru', debug: bool = False) -> str:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug("correct_text_with_tool")
    tool = get_language_tool(lang, debug)
    if tool:
        try:
            corrected = tool.correct(text)
            if debug:
                debug_logger.debug("Текст исправлен")
            return corrected
        except Exception as e:
            if debug:
                debug_logger.exception(f"Ошибка исправления: {e}")
    return text