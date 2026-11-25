# 123.py
import sys
import os
import json
import re
import threading
import webbrowser
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QGroupBox, QLabel, QTextEdit, QPushButton,
    QFileDialog, QMessageBox, QColorDialog, QCheckBox, QDoubleSpinBox,
    QComboBox, QInputDialog, QDialog
)
from PySide6.QtCore import Qt, QTimer

from processor import (
    read_file_content,
    detect_language,
    save_autosave,
    load_autosave,
    AUTOSAVE_FILE,
    get_text_stats,
    generate_wordcloud,
    export_to_pdf,
    save_profile,
    load_profile,
    docx_to_html,
    check_spelling,
    check_pip_updates,
    open_file_with_default_app,
)

from constants import STYLES_PATH, UI_LISTS_PATH, HELP_TEXTS_PATH, DOCUMENT_SETTINGS_PATH, DEFAULT_SETTINGS_PATH
from utils import load_json_file
from widgets import HelpWindow, SpinBoxEx, TextRedirector
from settings_manager import SettingsManager
from processing import ProcessingThread
from tabs import BasicTab, TitleTab, ExtraTab, ProfileTab, LogTab, PresentationTab, HomeTab
from ui_theme import DEFAULT_COLORS, normalize_colors
from project_manager import ProjectManager
from creation_wizard import CreationWizard
from quality_checks import inspect_text, format_report, fix_safe_whitespace
from backup_manager import BackupManager
from document_profile_manager import PROFILE_DIR
from editor_tools import ImageEditorDialog, TableEditorDialog
from markdown_editors import parse_markdown_table, parse_image_marker_options
from docx_comparison import compare_docx, format_comparison
from docx_to_slides import docx_to_presentation_markup
from slide_editor_dialog import SlideEditorDialog
from docx_merge import merge_docx_files

from logger import logger

HELP_TEXTS = load_json_file(HELP_TEXTS_PATH, {})
UI_LISTS = load_json_file(UI_LISTS_PATH, {})


def excepthook(exc_type, exc_value, exc_traceback):
    logger.critical("Необработанное исключение", exc_info=(exc_type, exc_value, exc_traceback))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = excepthook


def load_styles(accent_color="#7c4dff", colors=None):
    try:
        with open(STYLES_PATH, "r", encoding="utf-8") as f:
            template = f.read()
        palette = normalize_colors(colors, accent_color)
        replacements = {
            "%ACCENT_COLOR%": palette["accent"],
            "%BACKGROUND_COLOR%": palette["background"],
            "%SURFACE_COLOR%": palette["surface"],
            "%CONTROL_COLOR%": palette["control"],
            "%TEXT_COLOR%": palette["text"],
            "%BORDER_COLOR%": palette["border"],
        }
        for token, color in replacements.items():
            template = template.replace(token, color)
        return template
    except FileNotFoundError:
        return f"""
            QMainWindow {{ background-color: #121212; color: #e0e0e0; }}
            QPushButton {{ background-color: #2a2a2a; color: #e0e0e0; border: 1px solid #444; }}
            QPushButton:hover {{ background-color: {accent_color}; }}
        """


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("MainWindow инициализируется")
        self.setWindowTitle("Генератор ГОСТ-документов и презентаций")

        screen = QApplication.primaryScreen()
        available = screen.availableGeometry()
        norm_width = int(available.width() * 0.85)
        norm_height = int(available.height() * 0.85)
        min_width = min(1300, int(available.width() * 0.9))
        min_height = min(750, int(available.height() * 0.9))
        self.setMinimumSize(min_width, min_height)
        x = (available.width() - norm_width) // 2 + available.x()
        y = (available.height() - norm_height) // 2 + available.y()
        self.setGeometry(x, y, norm_width, norm_height)

        self.settings = SettingsManager()
        if os.path.exists(DOCUMENT_SETTINGS_PATH):
            self.settings.load_from_file(DOCUMENT_SETTINGS_PATH)
        else:
            self.settings.reset_to_defaults()

        self.processing_thread = None
        self.project_manager = ProjectManager()
        self.current_project_id = None
        self.current_project_name = ""
        self._build_ui()
        self.apply_style()

        sys.stdout = TextRedirector(self.log_tab.log_text)
        sys.stderr = TextRedirector(self.log_tab.log_text)

        self.check_autosave()
        self.start_autosave_timer()
        self.check_updates_background()
        self.on_mode_changed(self.mode_selector.currentIndex())
        self.tab_widget.setCurrentWidget(self.home_tab)
        self.home_tab.refresh(self.project_manager)
        logger.info("MainWindow инициализирован")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)

        left_widget = QWidget()
        left_widget.setFixedWidth(650)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        mode_hbox = QHBoxLayout()
        mode_hbox.addWidget(QLabel("Режим:"))
        self.mode_selector = QComboBox()
        self.mode_selector.addItems([
            "📄 Документ Word (ГОСТ)",
            "📊 Презентация (PPTX)",
        ])
        try:
            idx = int(self.settings.get("app_mode", 0))
        except Exception:
            idx = 0
        self.mode_selector.setCurrentIndex(0 if idx not in (0, 1) else idx)
        self.mode_selector.currentIndexChanged.connect(self.on_mode_changed)
        mode_hbox.addWidget(self.mode_selector, stretch=1)
        left_layout.addLayout(mode_hbox)

        self.tab_widget = QTabWidget()

        self.home_tab = HomeTab(self)
        self.basic_tab = BasicTab(self.settings, self, self.show_help)
        self.title_tab = TitleTab(self.settings, self.show_help)
        self.presentation_tab = PresentationTab(self.settings, self.show_help, self)
        self.extra_tab = ExtraTab(self.settings, self.show_help,
                                  UI_LISTS.get("spellcheck_langs", ["ru", "en", "auto"]))
        self.profile_tab = ProfileTab(self.settings, self.show_help, self)
        self.log_tab = LogTab(self.settings, self.show_help)

        self.tab_widget.addTab(self.home_tab, "Главная")
        self.tab_widget.addTab(self.basic_tab, "Основные")
        self.tab_widget.addTab(self.title_tab, "Титульные листы")
        self.tab_widget.addTab(self.presentation_tab, "Презентация")
        self.tab_widget.addTab(self.extra_tab, "Дополнительно")
        self.tab_widget.addTab(self.profile_tab, "Профили / Тема")
        self.tab_widget.addTab(self.log_tab, "Лог")

        left_layout.addWidget(self.tab_widget)
        main_layout.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6, 6, 6, 6)

        project_bar = QHBoxLayout()
        self.project_status_label = QLabel("Проект не сохранён")
        project_bar.addWidget(self.project_status_label, stretch=1)
        for caption, handler in (("Помощник создания", self.open_creation_wizard),
                                 ("Новый", self.new_project), ("Открыть", self.open_project),
                                 ("Сохранить", self.save_project), ("Недавние файлы", self.show_recent_documents)):
            button = QPushButton(caption)
            button.clicked.connect(handler)
            project_bar.addWidget(button)
        self.advanced_toggle = QCheckBox("Расширенные настройки")
        self.advanced_toggle.setChecked(bool(self.settings.get("advanced_settings", False)))
        self.advanced_toggle.toggled.connect(self.show_advanced_settings)
        project_bar.addWidget(self.advanced_toggle)
        right_layout.addLayout(project_bar)

        gost_group = QGroupBox("Параметры ГОСТ-оформления")
        gost_layout = QHBoxLayout(gost_group)

        self.cb_add_toc = QCheckBox("Автосодержание (TOC)")
        self.cb_add_toc.setChecked(self.settings.get("gost_toc", True))
        self.cb_add_toc.setToolTip("Автоматически вставить оглавление в начало документа. В Word потребуется нажать F9 для обновления.")
        self.cb_add_toc.stateChanged.connect(lambda s: self.settings.set("gost_toc", s == Qt.Checked))
        gost_layout.addWidget(self.cb_add_toc)

        gost_layout.addWidget(QLabel("Ширина рисунков:"))
        self.spin_img_width = QDoubleSpinBox()
        self.spin_img_width.setRange(5.0, 20.0)
        self.spin_img_width.setSingleStep(0.5)
        self.spin_img_width.setSuffix(" см")
        self.spin_img_width.setValue(self.settings.get("gost_img_width", 15.0))
        self.spin_img_width.setToolTip("На какую ширину растягивать картинку-заглушку.")
        self.spin_img_width.valueChanged.connect(lambda v: self.settings.set("gost_img_width", v))
        gost_layout.addWidget(self.spin_img_width)

        self.auto_caption_checkbox = QCheckBox("Автонумерация рисунков, таблиц и приложений")
        self.auto_caption_checkbox.setChecked(bool(self.settings.get("auto_number_captions", True)))
        self.auto_caption_checkbox.toggled.connect(
            lambda enabled: self.settings.set("auto_number_captions", bool(enabled)))
        gost_layout.addWidget(self.auto_caption_checkbox)

        btn_help_gost = QPushButton("❓ Как размечать текст для ИИ")
        btn_help_gost.clicked.connect(self.show_gost_help)
        gost_layout.addWidget(btn_help_gost)

        right_layout.addWidget(gost_group)

        self.text_area = QTextEdit()
        self.text_area.setAcceptRichText(False)
        self.text_area.setPlaceholderText(
            "Вставьте сюда текст от нейросети...\n\n"
            "Поддерживаются маркеры:\n"
            "[^Текст сноски] - сноска\n"
            "[IMAGE: Рисунок 1.1 - Название] - заглушка\n"
        )
        right_layout.addWidget(self.text_area, stretch=1)
        self.detected_type_label = QLabel("Тип материала: обычный текст")
        self.text_area.textChanged.connect(self.update_detected_content)
        right_layout.addWidget(self.detected_type_label)

        actions_group = QGroupBox("Действия")
        actions_layout = QVBoxLayout(actions_group)

        hbox_small = QHBoxLayout()
        small_actions = [
            ("📂 Загрузить", self.load_any_file, "load_file"),
            ("🗑 Очистить", self.clear_text, "clear_text"),
            ("🔍 Орфо", self.run_spellcheck, "spellcheck"),
            ("📊 Стат.", self.show_stats, "stats"),
            ("☁ Облако", self.generate_wordcloud_gui, "wordcloud"),
            ("📄 PDF", self.export_to_pdf_gui, "export_pdf"),
            ("🌐 HTML", self.preview_html, "preview_html"),
        ]
        for text, method, help_key in small_actions:
            btn = QPushButton(text)
            btn.clicked.connect(method)
            hbox_small.addWidget(btn)
            hbox_small.addWidget(self._create_help_button(help_key))
        actions_layout.addLayout(hbox_small)

        self.preflight_btn = QPushButton("Проверить материал")
        self.preflight_btn.clicked.connect(self.show_preflight_report)
        actions_layout.addWidget(self.preflight_btn)
        editor_buttons = QHBoxLayout()
        table_button = QPushButton("Редактор таблицы")
        table_button.clicked.connect(self.edit_table_at_cursor)
        image_button = QPushButton("Изображение…")
        image_button.clicked.connect(self.edit_image_at_cursor)
        editor_buttons.addWidget(table_button)
        editor_buttons.addWidget(image_button)
        compare_button = QPushButton("Сравнить два DOCX с образцом")
        compare_button.clicked.connect(self.compare_with_sample)
        editor_buttons.addWidget(compare_button)
        actions_layout.addLayout(editor_buttons)

        hbox_run = QHBoxLayout()
        self.run_btn = QPushButton("СОЗДАТЬ DOCX (ПО ГОСТ)")
        self.run_btn.setFixedHeight(50)
        accent = self.settings.get("accent_color", "#7c4dff")
        self.run_btn.setStyleSheet(
            f"font-size: 15px; font-weight: bold; "
            f"background-color: {accent}; color: white; border-radius: 5px;"
        )
        self.run_btn.clicked.connect(self.process_text)
        hbox_run.addWidget(self.run_btn, stretch=1)
        hbox_run.addWidget(self._create_help_button("create_docx"))
        actions_layout.addLayout(hbox_run)

        hbox_cancel = QHBoxLayout()
        self.cancel_btn = QPushButton("Отменить обработку")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel_processing)
        hbox_cancel.addWidget(self.cancel_btn, stretch=1)
        hbox_cancel.addWidget(self._create_help_button("cancel_processing"))
        actions_layout.addLayout(hbox_cancel)

        right_layout.addWidget(actions_group)
        main_layout.addWidget(right_widget, stretch=3)
        self._apply_advanced_visibility()

    def _set_project_status(self):
        if self.current_project_id:
            self.project_status_label.setText(f"Проект: {self.current_project_name}")
        else:
            self.project_status_label.setText("Проект не сохранён")

    def show_advanced_settings(self, enabled):
        self.settings.set("advanced_settings", bool(enabled))
        self._apply_advanced_visibility()

    def update_detected_content(self):
        report = inspect_text(self.text_area.toPlainText(), self.settings.get_all())
        self.detected_type_label.setText(f"Тип материала: {report['content_type']}")

    def show_preflight_report(self):
        text = self.text_area.toPlainText()
        report = inspect_text(text, self.settings.get_all())
        self._last_preflight_report = report
        dialog = QDialog(self)
        dialog.setWindowTitle("Проверка материала")
        dialog.resize(620, 480)
        layout = QVBoxLayout(dialog)
        counts = QLabel(f"Ошибок: {report['errors']} · Предупреждений: {report['warnings']}")
        layout.addWidget(counts)
        details = QTextEdit()
        details.setReadOnly(True)
        details.setPlainText(format_report(report))
        layout.addWidget(details, 1)
        buttons = QHBoxLayout()
        fix_button = QPushButton("Исправить лишние пробелы")
        fix_button.setVisible(not self.settings.get("markdown_mode", False)
                              and any(item["code"] == "extra_spaces" for item in report["findings"]))

        def fix_and_recheck():
            self.text_area.setPlainText(fix_safe_whitespace(
                self.text_area.toPlainText(), bool(self.settings.get("markdown_mode", False))))
            updated = inspect_text(self.text_area.toPlainText(), self.settings.get_all())
            self._last_preflight_report = updated
            counts.setText(f"Ошибок: {updated['errors']} · Предупреждений: {updated['warnings']}")
            details.setPlainText(format_report(updated))
            fix_button.setVisible(any(item["code"] == "extra_spaces" for item in updated["findings"]))

        fix_button.clicked.connect(fix_and_recheck)
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(dialog.accept)
        buttons.addWidget(fix_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        dialog.exec()

    def edit_table_at_cursor(self):
        cursor = self.text_area.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        caption_match = re.match(r"\s*\[TABLE:\s*(.*?)\s*\]", selected, re.I)
        caption = caption_match.group(1) if caption_match else ""
        rows = parse_markdown_table(selected)
        dialog = TableEditorDialog(self, rows=rows, caption=caption)
        if dialog.exec() != 1:
            return
        try:
            table = dialog.markdown()
        except ValueError as exc:
            QMessageBox.warning(self, "Таблица", str(exc))
            return
        if not selected:
            before = cursor.document().characterAt(max(0, cursor.position() - 1))
            after = cursor.document().characterAt(cursor.position())
            if cursor.position() and before != "\n":
                table = "\n\n" + table
            if after and after != "\n":
                table += "\n\n"
        cursor.insertText(table)
        self.text_area.setTextCursor(cursor)

    def edit_image_at_cursor(self):
        cursor = self.text_area.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n").strip()
        existing = parse_image_marker_options(selected)
        if existing:
            path, caption, width, alignment = existing
        else:
            path, caption, width, alignment = "", "", None, "center"
        dialog = ImageEditorDialog(self, path, caption,
                                   width if width is not None else self.settings.get("gost_img_width", 15.0), alignment)
        if dialog.exec() != 1:
            return
        try:
            marker = dialog.image_marker()
        except ValueError as exc:
            QMessageBox.warning(self, "Изображение", str(exc))
            return
        if not selected:
            before = cursor.document().characterAt(max(0, cursor.position() - 1))
            if cursor.position() and before != "\n":
                marker = "\n\n" + marker
            marker += "\n"
        cursor.insertText(marker)
        self.text_area.setTextCursor(cursor)

    def compare_with_sample(self):
        reference, _ = QFileDialog.getOpenFileName(self, "Выберите DOCX-образец", "", "Word (*.docx)")
        if not reference:
            return
        candidate, _ = QFileDialog.getOpenFileName(self, "Выберите документ для сравнения", "", "Word (*.docx)")
        if not candidate:
            return
        try:
            report = format_comparison(compare_docx(reference, candidate))
            QMessageBox.information(self, "Сравнение с образцом", report)
        except Exception as exc:
            QMessageBox.warning(self, "Сравнение с образцом", f"Не удалось сравнить документы:\n{exc}")

    def import_docx_to_presentation(self, path):
        try:
            markup = docx_to_presentation_markup(path, self.settings.get("ppt_max_items", 6))
            self.text_area.setPlainText(markup)
            self.settings.set("app_mode", 1)
            self.on_mode_changed(1)
            self.tab_widget.setCurrentWidget(self.presentation_tab)
            self.log_tab.append_log(f"Импортирован DOCX для создания слайдов: {path}")
        except Exception as exc:
            QMessageBox.warning(self, "Создание слайдов", f"Не удалось подготовить презентацию:\n{exc}")

    def edit_presentation_slides(self):
        dialog = SlideEditorDialog(self, self.text_area.toPlainText())
        if dialog.exec() == QDialog.Accepted:
            self.text_area.setPlainText(dialog.markup())

    def merge_docx_files_ui(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Выберите DOCX-файлы в нужном порядке", "", "Word (*.docx)")
        if len(paths) < 2:
            if paths:
                QMessageBox.information(self, "Объединение DOCX", "Выберите не менее двух файлов.")
            return
        output, _ = QFileDialog.getSaveFileName(self, "Сохранить объединённый DOCX", "merged.docx", "Word (*.docx)")
        if not output:
            return
        if not output.lower().endswith(".docx"):
            output += ".docx"
        try:
            result = merge_docx_files(paths, output)
            self._record_generated_document(result, "docx")
            QMessageBox.information(self, "Объединение DOCX", f"Объединённый документ создан:\n{result}")
        except Exception as exc:
            QMessageBox.warning(self, "Объединение DOCX", f"Не удалось объединить документы:\n{exc}")

    def _apply_advanced_visibility(self):
        if not hasattr(self, "tab_widget"):
            return
        advanced = bool(self.settings.get("advanced_settings", False))
        visibility = {
            self.title_tab: advanced,
            self.presentation_tab: advanced or self.settings.get("app_mode", 0) == 1,
            self.extra_tab: advanced,
            self.log_tab: advanced,
        }
        for widget, visible in visibility.items():
            self.tab_widget.setTabVisible(self.tab_widget.indexOf(widget), visible)
        for group in self.basic_tab.findChildren(QGroupBox, "advanced_basic_group"):
            group.setVisible(advanced)
        current = self.tab_widget.currentWidget()
        if current in visibility and not visibility[current]:
            self.tab_widget.setCurrentWidget(self.home_tab)

    def open_creation_wizard(self, default_mode=None):
        wizard = CreationWizard(self.settings, self, default_mode)
        if wizard.exec() != 1:
            return
        data = wizard.result_data()
        self.settings.set("app_mode", 1 if data["mode"] == "pptx" else 0)
        self.settings.set("document_profile", data["document_profile"] or "jasmine")
        if data["ppt_template_path"]:
            self.settings.set("ppt_template_path", data["ppt_template_path"])
        self.mode_selector.setCurrentIndex(self.settings.get("app_mode", 0))
        self.profile_tab.refresh_document_profiles(self.settings.get("document_profile", "jasmine"))
        self.text_area.setPlainText(data["text"])
        self.apply_style()
        self.process_text()

    def open_latest_project(self):
        projects = self.project_manager.list_projects()
        if not projects:
            QMessageBox.information(self, "Проекты", "Сохранённых проектов пока нет.")
            return
        self._load_project(projects[0]["project_id"])

    def _load_project(self, project_id):
        try:
            data = self.project_manager.load_project(project_id)
            self.text_area.setPlainText(data.get("text", ""))
            self._apply_settings_dict(data.get("settings", {}))
            self.profile_tab._refresh_palette_combo(self.settings.get("ui_palette_name", "Тёмная"))
            self.apply_style()
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.critical(self, "Проект", f"Не удалось открыть проект: {exc}")
            return
        self.current_project_id = data["project_id"]
        self.current_project_name = data.get("name", "Без названия")
        self._set_project_status()
        self.home_tab.refresh(self.project_manager)
        self.log_tab.append_log(f"Открыт проект: {self.current_project_name}")

    def save_project(self):
        name = self.current_project_name
        if not self.current_project_id:
            name, accepted = QInputDialog.getText(self, "Сохранить проект", "Название проекта:")
            if not accepted:
                return False
        try:
            saved = self.project_manager.save_project(
                name, self.text_area.toPlainText(), self._collect_settings_dict(),
                self.current_project_id,
            )
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Проект", f"Не удалось сохранить проект: {exc}")
            return False
        self.current_project_id = saved["project_id"]
        self.current_project_name = saved["name"]
        self._set_project_status()
        self.home_tab.refresh(self.project_manager)
        self.log_tab.append_log(f"Проект сохранён: {self.current_project_name}")
        return True

    def open_project(self):
        projects = self.project_manager.list_projects()
        if not projects:
            QMessageBox.information(self, "Проекты", "Сохранённых проектов пока нет.")
            return
        labels = [f"{item['name']} — {str(item.get('updated_at', ''))[:16]}" for item in projects]
        selected, accepted = QInputDialog.getItem(self, "Открыть проект", "Выберите проект:", labels, 0, False)
        if not accepted:
            return
        project = projects[labels.index(selected)]
        self._load_project(project["project_id"])

    def new_project(self):
        if self.text_area.toPlainText().strip():
            box = QMessageBox(self)
            box.setWindowTitle("Новый проект")
            box.setText("Сохранить текущий проект перед началом нового?")
            save_button = box.addButton("Сохранить", QMessageBox.AcceptRole)
            discard_button = box.addButton("Не сохранять", QMessageBox.DestructiveRole)
            box.addButton("Отмена", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is save_button and not self.save_project():
                return
            if box.clickedButton() not in (save_button, discard_button):
                return
        self.text_area.clear()
        self.current_project_id = None
        self.current_project_name = ""
        self._set_project_status()
        self.home_tab.refresh(self.project_manager)

    def show_recent_documents(self):
        recent = self.project_manager.recent_documents()
        if not recent:
            QMessageBox.information(self, "Недавние файлы", "Созданных файлов пока нет.")
            return
        labels = [f"{os.path.basename(item['path'])} — {item.get('kind', '').upper()} | {item['path']}"
                  for item in recent]
        selected, accepted = QInputDialog.getItem(self, "Недавние файлы", "Открыть документ:", labels, 0, False)
        if accepted:
            path = recent[labels.index(selected)]["path"]
            if not open_file_with_default_app(path):
                QMessageBox.warning(self, "Недавние файлы", f"Не удалось открыть файл:\n{path}")

    def create_backup(self):
        suggested = f"gost_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        path, _ = QFileDialog.getSaveFileName(self, "Создать резервную копию", suggested, "ZIP архив (*.zip)")
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        try:
            self._do_autosave()
            manager = BackupManager(
                os.path.dirname(os.path.abspath(__file__)), self.project_manager.data_dir,
                settings_files=(DEFAULT_SETTINGS_PATH, DOCUMENT_SETTINGS_PATH),
                profile_dir=PROFILE_DIR, autosave_file=AUTOSAVE_FILE,
            )
            included = manager.create_backup(path)
            QMessageBox.information(self, "Резервная копия",
                                    f"Архив создан. Сохранено файлов: {len(included)}\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Резервная копия", f"Не удалось создать архив: {exc}")

    def _record_generated_document(self, path, kind):
        try:
            self.project_manager.record_document(path, kind)
            self.home_tab.refresh(self.project_manager)
        except OSError as exc:
            self.log_tab.append_log(f"Не удалось обновить историю файлов: {exc}")

    def on_mode_changed(self, index):
        try:
            idx = int(index)
        except Exception:
            idx = 0
        self.settings.set("app_mode", idx)
        is_pptx = (idx == 1)

        try:
            self.presentation_tab.setVisible(is_pptx)
            self.basic_tab.setVisible(not is_pptx)
            self.title_tab.setVisible(not is_pptx)
        except Exception:
            pass

        try:
            if is_pptx:
                self.tab_widget.setCurrentWidget(self.presentation_tab)
            else:
                self.tab_widget.setCurrentWidget(self.basic_tab)
        except Exception:
            pass

        try:
            self.run_btn.setText("СОЗДАТЬ ПРЕЗЕНТАЦИЮ" if is_pptx else "СОЗДАТЬ DOCX (ПО ГОСТ)")
        except Exception:
            pass

        try:
            if is_pptx:
                self.text_area.setPlaceholderText(
                    "Вставьте текст презентации от нейросети...\n\n"
                    "Поддерживаются маркеры:\n"
                    "[SLIDE: title|bullets|image_right|image_left|image_full|chart|table|section|conclusion]\n"
                    "# Заголовок слайда\n"
                    "- пункт\n  - подпункт\n"
                    "[IMAGE: путь или описание]\n"
                    "[NOTES: текст доклада]\n"
                    "[CHART: bar] 2020: 100 ... [/CHART]\n"
                    "[TABLE] | a | b | ... [/TABLE]\n"
                    "--- (разделитель слайдов)"
                )
            else:
                self.text_area.setPlaceholderText(
                    "Вставьте сюда текст от нейросети...\n\n"
                    "Поддерживаются маркеры:\n"
                    "[^Текст сноски] - сноска внизу страницы\n"
                    "[IMAGE: Рисунок 1.1 - Название] - заглушка картинки\n"
                )
        except Exception:
            pass
        self._apply_advanced_visibility()

    def _create_help_button(self, key):
        btn = QPushButton("?")
        btn.setFixedSize(28, 28)
        accent = self.settings.get("accent_color", "#7c4dff")
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a; color: #e0e0e0;
                border: 1px solid #444444; border-radius: 4px;
                font-size: 10pt;
            }}
            QPushButton:hover {{ background-color: {accent}; color: white; }}
        """)
        btn.clicked.connect(lambda: self.show_help(key))
        return btn

    def show_help(self, key):
        text = HELP_TEXTS.get(key, "Нет описания.")
        win = HelpWindow(text, self)
        win.show()

    def show_gost_help(self):
        text = (
            "<b>Инструкция для нейросети (и для вас)</b><br><br>"
            "Чтобы программа правильно собрала документ по ГОСТ, размечайте текст специальными маркерами:<br><br>"
            "<b>1. Сноски внизу страницы:</b><br>"
            "Просто поставьте маркер после нужного слова: <code>[^Иванов И.И. Книга. С. 45.]</code><br><br>"
            "<b>2. Картинки:</b><br>"
            "Напишите маркер на отдельной строке: <code>[IMAGE: Рисунок 1.1 – Схема базы данных]</code><br>"
            "Программа вставит заглушку нужного размера и подпись.<br><br>"
            "<b>3. Заголовки:</b><br>"
            "Пишите заголовки с новой строки. Например: <code>ВВЕДЕНИЕ</code> или <code>1.1 Понятие веб-приложения</code><br><br>"
            "<b>4. Оглавление:</b><br>"
            "Если галочка 'Автосодержание' включена, оглавление добавится автоматически."
        )
        win = HelpWindow(text, self)
        win.setWindowTitle("Справка по ГОСТ-маркерам")
        win.resize(600, 400)
        win.show()

    def apply_style(self):
        all_settings = self.settings.get_all()
        colors = normalize_colors(
            all_settings.get("ui_colors"),
            all_settings.get("accent_color", "#7c4dff") if "ui_colors" not in all_settings else None,
        )
        self.settings.set("ui_colors", colors)
        self.settings.set("accent_color", colors["accent"])
        accent = colors["accent"]
        style = load_styles(accent, colors)
        self.setStyleSheet(style)
        self.run_btn.setStyleSheet(
            f"font-size: 15px; font-weight: bold; "
            f"background-color: {accent}; color: white; border-radius: 5px;"
        )
        self.basic_tab.update_accent_color()
        self.title_tab.update_accent_color()
        self.presentation_tab.update_accent_color()
        self.extra_tab.update_accent_color()
        self.profile_tab.update_accent_color()
        self.log_tab.update_accent_color()

    def load_any_file(self):
        filetypes = (
            "Все поддерживаемые (*.txt *.docx *.pdf *.html *.htm *.md *.odt *.pptx);;"
            "Текстовые (*.txt);;Word (*.docx);;PowerPoint (*.pptx);;PDF (*.pdf);;HTML (*.html *.htm);;"
            "Markdown (*.md);;OpenDocument (*.odt)"
        )
        filename, _ = QFileDialog.getOpenFileName(self, "Выберите файл", "", filetypes)
        if filename:
            try:
                text = read_file_content(filename)
                self.text_area.setPlainText(text)
                self.log_tab.append_log(f"Загружен: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать файл:\n{e}")

    def clear_text(self):
        self.text_area.clear()

    def run_spellcheck(self):
        text = self.text_area.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Нет текста", "Введите текст для проверки")
            return
        lang = self.settings.get("spellcheck_lang", "auto")
        if lang == "auto":
            lang = detect_language(text)
        errors = check_spelling(text, lang)
        if not errors:
            QMessageBox.information(self, "Орфография", "Орфографических ошибок не найдено")
            return
        msg = ""
        for err in errors:
            msg += f"Ошибка: {err['error']}\n"
            msg += f"Сообщение: {err['message']}\n"
            msg += f"Предложения: {', '.join(err['suggestions'])}\n"
            msg += "-" * 50 + "\n"
        win = HelpWindow(msg, self)
        win.setWindowTitle("Ошибки и предложения")
        win.resize(700, 500)
        win.show()

    def show_stats(self):
        text = self.text_area.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Нет текста", "Нет данных для статистики")
            return
        stats = get_text_stats(text)
        msg = (f"Слова: {stats['words']}\n"
               f"Символов с пробелами: {stats['chars_with_spaces']}\n"
               f"Символов без пробелов: {stats['chars_without_spaces']}\n"
               f"Предложений: {stats['sentences']}\n"
               f"Абзацев: {stats['paragraphs']}\n"
               f"Индекс читаемости: {stats['readability']} (0-100)")
        QMessageBox.information(self, "Статистика текста", msg)

    def generate_wordcloud_gui(self):
        text = self.text_area.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Нет текста", "Нечего визуализировать")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Сохранить облако слов", "", "PNG (*.png)")
        if save_path:
            if generate_wordcloud(text, save_path):
                QMessageBox.information(self, "Облако слов", f"Сохранено в {save_path}")
                webbrowser.open(save_path)
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось создать облако слов")

    def export_to_pdf_gui(self):
        docx_path, _ = QFileDialog.getOpenFileName(self, "Выберите DOCX", "", "Word (*.docx)")
        if docx_path:
            pdf_path = export_to_pdf(docx_path)
            if pdf_path:
                QMessageBox.information(self, "PDF", f"PDF сохранён:\n{pdf_path}")
                webbrowser.open(pdf_path)
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось конвертировать в PDF")

    def preview_html(self):
        docx_path, _ = QFileDialog.getOpenFileName(self, "Выберите DOCX", "", "Word (*.docx)")
        if docx_path:
            html_path = docx_to_html(docx_path)
            if html_path:
                webbrowser.open(html_path)
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось создать HTML-предпросмотр")

    def process_text(self):
        if self.processing_thread and self.processing_thread.isRunning():
            self.cancel_btn.setVisible(True)
            return

        mode = "pptx" if self.settings.get("app_mode", 0) == 1 else "docx"

        self.run_btn.setText("⏳ ОБРАБОТКА...")
        self.run_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.cancel_btn.setEnabled(True)
        self.log_tab.clear_log()

        text = self.text_area.toPlainText().strip()
        settings_dict = self._collect_settings_dict()

        if mode == "docx":
            split_enabled = self.settings.get("split_enabled", False)
            split_marker = self.settings.get("split_marker", "---")
        else:
            split_enabled = False
            split_marker = "---"

        ask_name = self.settings.get("ask_filename", False)
        debug_mode = self.settings.get("debug_mode", False)

        logger.info(f"Начало обработки, режим={mode}, длина={len(text)}, "
                    f"clone_mode={self.settings.get('ppt_use_clone_mode', False)}")

        self.processing_thread = ProcessingThread(
            self, text, settings_dict, split_enabled, split_marker,
            ask_name, debug_mode, mode=mode,
        )
        self.processing_thread.progress.connect(self.log_tab.append_log)
        self.processing_thread.finished.connect(self.on_processing_finished)
        self.processing_thread.document_created.connect(self._record_generated_document)
        self.processing_thread.start()

    def cancel_processing(self):
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.cancel_flag = True
            self.cancel_btn.setEnabled(False)
            self.log_tab.append_log("⏳ Отмена...")
            logger.info("Запрошена отмена обработки")

    def on_processing_finished(self, success, message):
        logger.info(f"Обработка завершена: success={success}, message={message}")
        self.run_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(True)
        is_pptx = self.settings.get("app_mode", 0) == 1
        self.run_btn.setText("СОЗДАТЬ ПРЕЗЕНТАЦИЮ" if is_pptx else "СОЗДАТЬ DOCX (ПО ГОСТ)")
        if success:
            QMessageBox.information(self, "Готово", message)
        else:
            QMessageBox.critical(self, "Ошибка", message)

    def save_current_profile(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить профиль", "", "JSON (*.json)")
        if path:
            data = self._collect_settings_dict()
            if save_profile(path, data):
                QMessageBox.information(self, "Успех", "Профиль сохранён")
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось сохранить профиль")

    def load_profile_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить профиль", "", "JSON (*.json)")
        if path:
            data = load_profile(path)
            if data:
                self._apply_settings_dict(data)
                self.sync_ui_from_settings()
                QMessageBox.information(self, "Успех", "Профиль загружен")
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось загрузить профиль")

    def reset_to_default(self):
        reply = QMessageBox.question(self, "Сброс", "Сбросить все настройки к значениям по умолчанию?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.settings.reset_to_defaults()
            self.sync_ui_from_settings()
            self.apply_style()
            QMessageBox.information(self, "Сброс", "Настройки сброшены")

    def save_appearance_settings(self):
        """Persist interface colors without changing document profile data."""
        try:
            data = self._collect_settings_dict()
            if not self.settings.save_to_file(DOCUMENT_SETTINGS_PATH, data):
                raise OSError("Не удалось записать файл настроек")
            QMessageBox.information(self, "Оформление", "Настройки интерфейса сохранены.")
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Оформление", f"Не удалось сохранить настройки: {exc}")
            return False

    def load_json_settings(self):
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить JSON", "", "JSON (*.json)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._apply_settings_dict(data)
                self.sync_ui_from_settings()
                QMessageBox.information(self, "Успех", "Настройки загружены")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить: {e}")

    def save_json_settings(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить JSON", "", "JSON (*.json)")
        if path:
            try:
                data = self._collect_settings_dict()
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                QMessageBox.information(self, "Успех", "Настройки сохранены")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

    def _collect_settings_dict(self):
        data = self.settings.get_all().copy()
        data["output_folder"] = self.basic_tab.current_folder
        data["saved_folders"] = self.basic_tab.saved_folders
        data["filename_template"] = self.settings.get_filename_template()

        data["gost_toc"] = self.cb_add_toc.isChecked()
        data["gost_img_width"] = self.spin_img_width.value()

        title_data = self.title_tab.get_title_data()
        title_data["enabled"] = self.settings.get("title_enabled", False)
        data["title_page"] = title_data
        data["debug_mode"] = self.settings.get("debug_mode", False)

        # ppt_presentation — как единый блок для сохранения
        ppt_data = self.presentation_tab.get_presentation_data()
        data["ppt_presentation"] = ppt_data

        # Дублируем критичные ключи в плоский settings для worker-процесса
        data["ppt_use_clone_mode"] = bool(ppt_data.get("use_clone_mode", False))
        data["ppt_clone_map"] = dict(ppt_data.get("clone_map", {}) or {})

        return data

    def _apply_settings_dict(self, data):
        skip = ["output_folder", "saved_folders", "title_page", "filename_template",
                "gost_toc", "gost_img_width", "ppt_presentation", "app_mode",
                "ppt_use_clone_mode", "ppt_clone_map"]
        for key in data:
            if key not in skip:
                self.settings.set(key, data[key])

        # Старые пользовательские наборы хранили только accent_color.
        if "accent_color" in data and "ui_colors" not in data:
            colors = normalize_colors(self.settings.get("ui_colors"), data["accent_color"])
            colors["accent"] = data["accent_color"]
            self.settings.set("ui_colors", normalize_colors(colors))

        if "output_folder" in data:
            self.basic_tab.current_folder = data["output_folder"]
            self.basic_tab.saved_folders = data.get("saved_folders", [])
            self.basic_tab._update_folder_combo()
        if "title_page" in data:
            self.title_tab.apply_title_data(data["title_page"])
            if "enabled" in data["title_page"]:
                self.settings.set("title_enabled", data["title_page"]["enabled"])
        if "gost_toc" in data:
            self.cb_add_toc.setChecked(data["gost_toc"])
            self.settings.set("gost_toc", data["gost_toc"])
        if "gost_img_width" in data:
            self.spin_img_width.setValue(data["gost_img_width"])
            self.settings.set("gost_img_width", data["gost_img_width"])
        if "ppt_presentation" in data:
            self.presentation_tab.apply_presentation_data(data["ppt_presentation"])
        # Плоские ключи тоже прокидываем в settings (если пришли из старого профиля)
        if "ppt_use_clone_mode" in data:
            self.settings.set("ppt_use_clone_mode", bool(data["ppt_use_clone_mode"]))
        if "ppt_clone_map" in data:
            self.settings.set("ppt_clone_map", dict(data["ppt_clone_map"]))
        if "app_mode" in data:
            try:
                idx = int(data["app_mode"])
            except Exception:
                idx = 0
            self.mode_selector.setCurrentIndex(0 if idx not in (0, 1) else idx)
            self.settings.set("app_mode", idx)

        self.sync_ui_from_settings()

    def sync_ui_from_settings(self):
        self.basic_tab.sync_ui_from_settings()
        self.title_tab.sync_ui_from_settings()
        self.presentation_tab.sync_ui_from_settings()
        self.extra_tab.sync_ui_from_settings()
        if hasattr(self, "advanced_toggle"):
            self.advanced_toggle.blockSignals(True)
            self.advanced_toggle.setChecked(bool(self.settings.get("advanced_settings", False)))
            self.advanced_toggle.blockSignals(False)
            self._apply_advanced_visibility()
        if hasattr(self, "profile_tab") and hasattr(self.profile_tab, "refresh_document_profiles"):
            self.profile_tab.refresh_document_profiles(self.settings.get("document_profile", "jasmine"))
        if hasattr(self.profile_tab, "update_url_edit"):
            self.profile_tab.update_url_edit.blockSignals(True)
            self.profile_tab.update_url_edit.setText(self.settings.get("update_manifest_url", ""))
            self.profile_tab.update_url_edit.blockSignals(False)

        self.cb_add_toc.setChecked(self.settings.get("gost_toc", True))
        self.spin_img_width.setValue(self.settings.get("gost_img_width", 15.0))
        self.auto_caption_checkbox.setChecked(bool(self.settings.get("auto_number_captions", True)))

        if hasattr(self.profile_tab, 'debug_checkbox'):
            self.profile_tab.debug_checkbox.setChecked(self.settings.get("debug_mode", False))

        try:
            idx = int(self.settings.get("app_mode", 0))
            self.mode_selector.setCurrentIndex(0 if idx not in (0, 1) else idx)
        except Exception:
            pass

    def start_autosave_timer(self):
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self._do_autosave)
        self.autosave_timer.start(30000)

    def _do_autosave(self):
        try:
            text = self.text_area.toPlainText().strip()
            settings = self._collect_settings_dict()
            save_autosave(text, settings)
        except Exception as e:
            print(f"Автосохранение: {e}")

    def check_autosave(self):
        text, settings = load_autosave()
        if text and settings:
            reply = QMessageBox.question(self, "Восстановление",
                                         "Обнаружен сохранённый сеанс. Восстановить?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.text_area.setPlainText(text)
                self._apply_settings_dict(settings)
                self.sync_ui_from_settings()
            else:
                try:
                    os.remove(AUTOSAVE_FILE)
                except Exception:
                    pass

    def check_updates_background(self):
        def do_check():
            outdated = check_pip_updates()
            if outdated:
                self.log_tab.append_log(
                    "⚠️ Доступны обновления библиотек. Выполните pip install --upgrade ..."
                )
        threading.Thread(target=do_check, daemon=True).start()

    def closeEvent(self, event):
        try:
            data = self._collect_settings_dict()
            self.settings.save_to_file(DOCUMENT_SETTINGS_PATH, data)
        except Exception:
            pass
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())
