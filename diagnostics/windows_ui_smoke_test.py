"""Диагностика интерфейса на Windows.
Запуск: py -3.10 diagnostics\\windows_ui_smoke_test.py
Результат: diagnostics\\ui_smoke_report.txt
"""
from __future__ import annotations
import json
import platform
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
report = []


def record(name, ok, detail=''):
    report.append({'test': name, 'ok': bool(ok), 'detail': str(detail)})


record('Python version', sys.version_info >= (3, 10), sys.version.split()[0])
record('Windows', platform.system() == 'Windows', platform.platform())

try:
    import PySide6
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtCore import Qt
    record('PySide6 import', True, PySide6.__version__)
except Exception as exc:
    record('PySide6 import', False, repr(exc))
    QApplication = None

if QApplication is not None:
    try:
        app = QApplication.instance() or QApplication([])
        from settings_manager import SettingsManager
        from tabs.profile_tab import ProfileTab
        settings = SettingsManager()
        tab = ProfileTab(settings, lambda *_: None)
        record('Profile tab creates', True, f'widgets={len(tab.findChildren(QWidget))}')
        combo = tab.document_profile_combo
        ids = [combo.itemData(i) for i in range(combo.count())]
        record('Built-in profiles listed', {'jasmine', 'legacy_gost'}.issubset(set(ids)), ids)
        if 'legacy_gost' in ids:
            combo.setCurrentIndex(ids.index('legacy_gost'))
            record('Profile selection updates settings', settings.get('document_profile') == 'legacy_gost',
                   settings.get('document_profile'))
        tab.close()
        app.processEvents()
    except Exception:
        record('Profile tab UI smoke test', False, traceback.format_exc())

try:
    from document_profile_manager import list_profiles
    profiles = list_profiles()
    record('Profile JSON files load', len(profiles) >= 2,
           [p.get('profile_id') for p in profiles])
except Exception:
    record('Profile JSON files load', False, traceback.format_exc())

try:
    from pptx import Presentation
    from docx import Document
    record('DOCX/PPTX libraries', True, 'python-docx and python-pptx imported')
except Exception:
    record('DOCX/PPTX libraries', False, traceback.format_exc())

out = ROOT / 'diagnostics' / 'ui_smoke_report.txt'
out.write_text('\n'.join(
    f"{'PASS' if item['ok'] else 'FAIL'} | {item['test']} | {item['detail']}"
    for item in report
), encoding='utf-8')
print(out.read_text(encoding='utf-8'))
print(f'\nОтчёт сохранён: {out}')
if any(not item['ok'] for item in report):
    raise SystemExit(1)
