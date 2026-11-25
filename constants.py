# constants.py
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Пути к JSON-файлам
DEFAULT_SETTINGS_PATH = os.path.join(SCRIPT_DIR, "default_settings.json")
UI_LISTS_PATH = os.path.join(SCRIPT_DIR, "ui_lists.json")
HELP_TEXTS_PATH = os.path.join(SCRIPT_DIR, "help_texts.json")
DOCUMENT_SETTINGS_PATH = os.path.join(SCRIPT_DIR, "document_settings.json")
AUTOSAVE_PATH = os.path.join(SCRIPT_DIR, "autosave.json")

# Путь к файлу стилей
STYLES_PATH = os.path.join(SCRIPT_DIR, "styles.qss")

# Путь к картинке-заглушке для рисунков
PLACEHOLDER_IMAGE_PATH = os.path.join(SCRIPT_DIR, "placeholder.png")