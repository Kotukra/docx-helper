# processor/__init__.py
# Публичный API пакета processor.
# Экспортирует всё, что импортируется из 123.py, processing_thread.py, worker.py.

# ---------- autosave ----------
from .autosave import (
    save_autosave,
    load_autosave,
    AUTOSAVE_FILE,
)

# ---------- file_io ----------
from .file_io import (
    read_file_content,
    save_profile,
    load_profile,
    docx_to_html,
    export_to_pdf,
    load_settings,
    open_file_with_default_app,
)

# ---------- keywords ----------
from .keywords import (
    detect_language,
    generate_filename_adaptive,
    generate_filename_combined,
    generate_custom_filename,
    sanitize_filename,
    split_text_by_marker,
)

# ---------- text_cleaning ----------
from .text_cleaning import (
    enhanced_clean_text,
    clean_text,
    find_extra_spaces,
    find_extra_enters,
    detect_non_russian_words,
)

# ---------- stats ----------
from .stats import (
    get_text_stats,
    generate_wordcloud,
)

# ---------- spellcheck ----------
from .spellcheck import (
    check_spelling,
    correct_text_with_tool,
)

# ---------- updates ----------
from .updates import (
    check_pip_updates,
    notify_updates,
)

# ---------- workers ----------
from .worker import create_document_worker
from .ppt_worker import create_presentation_worker

# ---------- doc_creator ----------
from .doc_creator import (
    create_word_document,
    batch_process_documents,
    get_title_for_part,
)

# ---------- ГОСТ-примитивы (без add_real_footnote) ----------
from .gost_builder import (
    setup_gost_styles,
    insert_image_placeholder,
    add_gost_table,
    add_table_of_contents,
)

# ---------- Новые модули: сноски и нумерация страниц ----------
from .footnotes import (
    FootnoteManager,
    add_text_with_footnotes,
)
from .page_numbers import add_page_numbers