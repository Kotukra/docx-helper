# processor/stats.py
import re
from typing import Dict
from .availability import WORDCLOUD_AVAILABLE
from .constants import STOP_WORDS
from logger import get_debug_logger

def get_text_stats(text: str, debug: bool = False) -> Dict:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug("get_text_stats: начало")
    words = re.findall(r'\b\w+\b', text, re.UNICODE)
    word_count = len(words)
    chars_with_spaces = len(text)
    chars_without_spaces = len(re.sub(r'\s', '', text))
    sentences = [s for s in re.split(r'[.!?]+', text) if s.strip()]
    sentence_count = len(sentences)
    paragraphs = [p for p in text.split('\n') if p.strip()]
    paragraph_count = len(paragraphs)
    if sentence_count > 0 and word_count > 0:
        avg_words = word_count / sentence_count
        complex_words = sum(1 for w in words if len(w) > 6)
        complex_ratio = complex_words / word_count
        readability = 206.835 - 1.3 * avg_words - 60.1 * complex_ratio
        readability = max(0, min(100, readability))
    else:
        readability = 0
    result = {
        'words': word_count,
        'chars_with_spaces': chars_with_spaces,
        'chars_without_spaces': chars_without_spaces,
        'sentences': sentence_count,
        'paragraphs': paragraph_count,
        'readability': round(readability, 2)
    }
    if debug:
        debug_logger.debug(f"Статистика: {result}")
    return result

def generate_wordcloud(text: str, output_image_path: str,
                       width: int = 800, height: int = 600,
                       background_color: str = 'white', max_words: int = 200,
                       debug: bool = False) -> bool:
    if debug:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"generate_wordcloud: {output_image_path}")
    if not WORDCLOUD_AVAILABLE:
        if debug:
            debug_logger.error("wordcloud не установлен")
        print("wordcloud не установлен")
        return False
    try:
        from wordcloud import WordCloud
        import matplotlib.pyplot as plt
        words = re.findall(r'\b[а-яёa-z]+\b', text.lower(), re.UNICODE)
        filtered = [w for w in words if w not in STOP_WORDS and len(w) > 2]
        clean_text = ' '.join(filtered) or text
        if debug:
            debug_logger.debug(f"Очищенный текст для облака: {len(clean_text)} символов")
        wc = WordCloud(width=width, height=height, background_color=background_color,
                       max_words=max_words, collocations=False).generate(clean_text)
        plt.figure(figsize=(width/100, height/100))
        plt.imshow(wc, interpolation='bilinear')
        plt.axis('off')
        plt.savefig(output_image_path, dpi=100, bbox_inches='tight')
        plt.close()
        if debug:
            debug_logger.debug("Облако слов сохранено")
        return True
    except Exception as e:
        if debug:
            debug_logger.exception(f"WordCloud ошибка: {e}")
        print(f"WordCloud error: {e}")
        return False