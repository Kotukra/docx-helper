# autosave.py
import os
import json
import tempfile
from typing import Optional, Dict, Tuple

def get_autosave_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    autosave_path = os.path.join(script_dir, "autosave.json")
    try:
        with open(autosave_path, 'a') as f:
            pass
        return autosave_path
    except:
        return os.path.join(tempfile.gettempdir(), "doc_processor_autosave.json")

AUTOSAVE_FILE = get_autosave_path()

def save_autosave(text: str, settings: Dict) -> None:
    try:
        with open(AUTOSAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump({"text": text, "settings": settings}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка автосохранения: {e}")

def load_autosave() -> Tuple[Optional[str], Optional[Dict]]:
    if not os.path.exists(AUTOSAVE_FILE):
        return None, None
    try:
        with open(AUTOSAVE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("text"), data.get("settings")
    except Exception:
        return None, None