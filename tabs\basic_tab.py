import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QComboBox, QCheckBox, QPushButton, QFileDialog,
    QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt

from widgets import SpinBoxEx
from constants import UI_LISTS_PATH
from utils import load_json_file


class BasicTab(QWidget):
    def __init__(self, settings_manager, parent_window, help_callback):
        super().__init__(parent_window)
        self.settings = settings_manager
        self.parent_window = parent_window
        self.help_callback = help_callback

        ui_lists = load_json_file(UI_LISTS_PATH, {})
        self.font_names = ui_lists.get("font_names", ["Times New Roman", "Arial", "Calibri", "Verdana", "Georgia"])
        self.alignments = ui_lists.get("alignments", ["left", "center", "right", "justify"])

        self.saved_folders = self.settings.get("saved_folders", [])
        self.current_folder = self.settings.get("output_folder", "")

        self._build_ui()
        self.sync_ui_from_settings()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)

        # ---- Папка сохранения ----
        g = QGroupBox("Папка сохранения")
        g_layout = QVBoxLayout(g)
        self.folder_combo = QComboBox()
        self.folder_combo.setEditable(True)
        self.folder_combo.currentTextChanged.connect(self.on_folder_selected)
        self._update_folder_combo()
        g_layout.addWidget(self.folder_combo)
        btn_frame = QHBoxLayout()
        btn_choose = QPushButton("📁 Выбрать")
        btn_choose.clicked.connect(self.choose_folder)
        btn_frame.addWidget(btn_choose)
        btn_frame.addWidget(self._create_help_button("folder_choose"))
        btn_add = QPushButton("➕ Добавить")
        btn_add.clicked.connect(self.add_current_folder)
        btn_frame.addWidget(btn_add)
        btn_frame.addWidget(self._create_help_button("folder_add"))
        btn_remove = QPushButton("❌ Удалить")
        btn_remove.clicked.connect(self.remove_selected_folder)
        btn_frame.addWidget(btn_remove)
        btn_frame.addWidget(self._create_help_button("folder_remove"))
        g_layout.addLayout(btn_frame)
        container_layout.addWidget(g)

        # ---- Шрифт и выравнивание ----
        g = QGroupBox("Шрифт и выравнивание")
        g_layout = QGridLayout(g)
        row = 0
        g_layout.addWidget(QLabel("Шрифт:"), row, 0)
        self.font_name_combo = QComboBox()
        self.font_name_combo.setObjectName("font_name")
        self.font_name_combo.addItems(self.font_names)
        self.font_name_combo.setCurrentText(self.settings.get("font_name", "Times New Roman"))
        self.font_name_combo.currentTextChanged.connect(lambda v: self.settings.set("font_name", v))
        g_layout.addWidget(self.font_name_combo, row, 1)
        g_layout.addWidget(self._create_help_button("font_name"), row, 2)
        row += 1

        g_layout.addWidget(QLabel("Размер (пт):"), row, 0)
        self.font_size_spin = SpinBoxEx(8, 72, 1, 0, self.settings.get("font_size", 14))
        self.font_size_spin.setObjectName("font_size")
        self.font_size_spin.valueChanged.connect(lambda v: self.settings.set("font_size", v))
        g_layout.addWidget(self.font_size_spin, row, 1)
        g_layout.addWidget(self._create_help_button("font_size"), row, 2)
        row += 1

        g_layout.addWidget(QLabel("Выравнивание:"), row, 0)
        self.alignment_combo = QComboBox()
        self.alignment_combo.setObjectName("alignment")
        self.alignment_combo.addItems(self.alignments)
        self.alignment_combo.setCurrentText(self.settings.get("alignment", "justify"))
        self.alignment_combo.currentTextChanged.connect(lambda v: self.settings.set("alignment", v))
        g_layout.addWidget(self.alignment_combo, row, 1)
        container_layout.addWidget(g)

        # ---- Отступы ----
        g = QGroupBox("Отступы (см)")
        g.setObjectName("advanced_basic_group")
        g_layout = QGridLayout(g)
        row = 0
        for label, key in [("Красная строка:", "first_line_indent"),
                           ("Слева:", "left_indent"),
                           ("Справа:", "right_indent")]:
            g_layout.addWidget(QLabel(label), row, 0)
            spin = SpinBoxEx(-10, 20, 0.1, 1, self.settings.get(key, 0.0))
            spin.setObjectName(key)
            spin.valueChanged.connect(lambda v, k=key: self.settings.set(k, v))
            g_layout.addWidget(spin, row, 1)
            g_layout.addWidget(self._create_help_button(key), row, 2)
            row += 1
        container_layout.addWidget(g)

        # ---- Размер страницы ----
        g = QGroupBox("Размер страницы (см)")
        g.setObjectName("advanced_basic_group")
        g_layout = QGridLayout(g)
        row = 0
        for label, key in [("Ширина:", "page_width"), ("Высота:", "page_height")]:
            g_layout.addWidget(QLabel(label), row, 0)
            spin = SpinBoxEx(5, 100, 0.1, 1, self.settings.get(key, 21.0))
            spin.setObjectName(key)
            spin.valueChanged.connect(lambda v, k=key: self.settings.set(k, v))
            g_layout.addWidget(spin, row, 1)
            g_layout.addWidget(self._create_help_button(key), row, 2)
            row += 1
        container_layout.addWidget(g)

        # ---- Поля ----
        g = QGroupBox("Поля (см)")
        g.setObjectName("advanced_basic_group")
        g_layout = QGridLayout(g)
        row = 0
        for label, key in [("Верхнее:", "margin_top"), ("Нижнее:", "margin_bottom"),
                           ("Левое:", "margin_left"), ("Правое:", "margin_right")]:
            g_layout.addWidget(QLabel(label), row, 0)
            spin = SpinBoxEx(0, 10, 0.1, 1, self.settings.get(key, 2.0))
            spin.setObjectName(key)
            spin.valueChanged.connect(lambda v, k=key: self.settings.set(k, v))
            g_layout.addWidget(spin, row, 1)
            g_layout.addWidget(self._create_help_button(key), row, 2)
            row += 1
        container_layout.addWidget(g)

        # ---- Форматирование абзацев ----
        g = QGroupBox("Форматирование абзацев")
        g.setObjectName("advanced_basic_group")
        g_layout = QGridLayout(g)
        row = 0
        g_layout.addWidget(QLabel("Межстрочный интервал (множитель):"), row, 0)
        spin = SpinBoxEx(0.5, 3.0, 0.5, 1, self.settings.get("line_spacing_multiple", 1.0))
        spin.setObjectName("line_spacing_multiple")
        spin.valueChanged.connect(lambda v: self.settings.set("line_spacing_multiple", v))
        g_layout.addWidget(spin, row, 1)
        g_layout.addWidget(self._create_help_button("line_spacing_multiple"), row, 2)
        row += 1

        g_layout.addWidget(QLabel("Интервал перед (пт):"), row, 0)
        spin_before = SpinBoxEx(0, 100, 1, 0, self.settings.get("space_before", 0))
        spin_before.setObjectName("space_before")
        spin_before.valueChanged.connect(lambda v: self.settings.set("space_before", v))
        g_layout.addWidget(spin_before, row, 1)
        g_layout.addWidget(self._create_help_button("space_before"), row, 2)
        row += 1

        g_layout.addWidget(QLabel("Интервал после (пт):"), row, 0)
        spin_after = SpinBoxEx(0, 100, 1, 0, self.settings.get("space_after", 0))
        spin_after.setObjectName("space_after")
        spin_after.valueChanged.connect(lambda v: self.settings.set("space_after", v))
        g_layout.addWidget(spin_after, row, 1)
        g_layout.addWidget(self._create_help_button("space_after"), row, 2)
        row += 1

        cb_keep = QCheckBox("Не разрывать абзац")
        cb_keep.setObjectName("keep_together")
        cb_keep.setChecked(self.settings.get("keep_together", False))
        cb_keep.stateChanged.connect(lambda s: self.settings.set("keep_together", s == Qt.Checked))
        g_layout.addWidget(cb_keep, row, 0, 1, 1)
        g_layout.addWidget(self._create_help_button("keep_together"), row, 1, 1, 1)
        row += 1

        cb_next = QCheckBox("Привязать к следующему")
        cb_next.setObjectName("keep_with_next")
        cb_next.setChecked(self.settings.get("keep_with_next", False))
        cb_next.stateChanged.connect(lambda s: self.settings.set("keep_with_next", s == Qt.Checked))
        g_layout.addWidget(cb_next, row, 0, 1, 1)
        g_layout.addWidget(self._create_help_button("keep_with_next"), row, 1, 1, 1)
        container_layout.addWidget(g)

        # ---- Разделение текста ----
        g = QGroupBox("Разделение текста")
        g.setObjectName("advanced_basic_group")
        g_layout = QVBoxLayout(g)
        hbox_split = QHBoxLayout()
        cb_split = QCheckBox("Включить разделение")
        cb_split.setObjectName("split_enabled")
        cb_split.setChecked(self.settings.get("split_enabled", False))
        cb_split.stateChanged.connect(lambda s: self.settings.set("split_enabled", s == Qt.Checked))
        hbox_split.addWidget(cb_split)
        hbox_split.addWidget(self._create_help_button("split_enabled"))
        g_layout.addLayout(hbox_split)

        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("Маркер:"))
        self.split_marker_edit = QLineEdit(self.settings.get("split_marker", "---"))
        self.split_marker_edit.setObjectName("split_marker")
        self.split_marker_edit.textChanged.connect(lambda v: self.settings.set("split_marker", v))
        hbox.addWidget(self.split_marker_edit)
        hbox.addWidget(self._create_help_button("split_marker"))
        g_layout.addLayout(hbox)
        container_layout.addWidget(g)

        # ============================================================
        # ==== НОВЫЙ БЛОК: НУМЕРАЦИЯ СТРАНИЦ ====
        # ============================================================
        g = QGroupBox("Нумерация страниц")
        g.setObjectName("advanced_basic_group")
        g_layout = QGridLayout(g)
        row = 0

        # Включить нумерацию
        cb_pn = QCheckBox("Включить нумерацию страниц")
        cb_pn.setObjectName("page_numbers")
        cb_pn.setChecked(self.settings.get("page_numbers", True))
        cb_pn.stateChanged.connect(
            lambda s: self.settings.set("page_numbers", s == Qt.Checked))
        g_layout.addWidget(cb_pn, row, 0, 1, 3)
        row += 1

        # Без номера на титуле
        cb_skip = QCheckBox("Без номера на титульном листе")
        cb_skip.setObjectName("page_numbers_skip_first")
        cb_skip.setChecked(self.settings.get("page_numbers_skip_first", True))
        cb_skip.stateChanged.connect(
            lambda s: self.settings.set("page_numbers_skip_first", s == Qt.Checked))
        g_layout.addWidget(cb_skip, row, 0, 1, 3)
        row += 1

        # Стартовый номер
        g_layout.addWidget(QLabel("Стартовый номер:"), row, 0)
        spin_start = SpinBoxEx(1, 9999, 1, 0,
                               self.settings.get("page_numbers_start", 1))
        spin_start.setObjectName("page_numbers_start")
        spin_start.valueChanged.connect(
            lambda v: self.settings.set("page_numbers_start", int(v)))
        g_layout.addWidget(spin_start, row, 1)
        row += 1

        # Положение (footer / header)
        g_layout.addWidget(QLabel("Положение:"), row, 0)
        combo_pos = QComboBox()
        combo_pos.setObjectName("page_numbers_position")
        combo_pos.addItems(["footer", "header"])
        cur_pos = self.settings.get("page_numbers_position", "footer")
        if combo_pos.findText(cur_pos) >= 0:
            combo_pos.setCurrentText(cur_pos)
        combo_pos.currentTextChanged.connect(
            lambda v: self.settings.set("page_numbers_position", v))
        g_layout.addWidget(combo_pos, row, 1)
        row += 1

        # Выравнивание
        g_layout.addWidget(QLabel("Выравнивание:"), row, 0)
        combo_align = QComboBox()
        combo_align.setObjectName("page_numbers_align")
        combo_align.addItems(["center", "left", "right"])
        cur_align = self.settings.get("page_numbers_align", "center")
        if combo_align.findText(cur_align) >= 0:
            combo_align.setCurrentText(cur_align)
        combo_align.currentTextChanged.connect(
            lambda v: self.settings.set("page_numbers_align", v))
        g_layout.addWidget(combo_align, row, 1)
        row += 1

        container_layout.addWidget(g)
        # ============================================================
        # ==== /НОВЫЙ БЛОК ====
        # ============================================================

        scroll.setWidget(container)
        layout.addWidget(scroll)

    # ---- Методы для папок ----
    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if folder:
            self.current_folder = folder
            if folder not in self.saved_folders:
                self.saved_folders.append(folder)
            self._update_folder_combo()
            self.settings.set("output_folder", folder)
            self.settings.set("saved_folders", self.saved_folders)

    def add_current_folder(self):
        folder = self.folder_combo.currentText().strip()
        if folder and folder not in self.saved_folders:
            self.saved_folders.append(folder)
            self._update_folder_combo()
            self.settings.set("saved_folders", self.saved_folders)

    def remove_selected_folder(self):
        folder = self.folder_combo.currentText().strip()
        if folder in self.saved_folders:
            self.saved_folders.remove(folder)
            self._update_folder_combo()
            if self.saved_folders:
                self.current_folder = self.saved_folders[0]
            else:
                self.current_folder = ""
            self.settings.set("output_folder", self.current_folder)
            self.settings.set("saved_folders", self.saved_folders)

    def on_folder_selected(self, text):
        if text in self.saved_folders:
            self.current_folder = text
            self.settings.set("output_folder", text)

    def _update_folder_combo(self):
        self.folder_combo.clear()
        self.folder_combo.addItems(self.saved_folders)
        if self.current_folder in self.saved_folders:
            self.folder_combo.setCurrentText(self.current_folder)
        elif self.saved_folders:
            self.folder_combo.setCurrentText(self.saved_folders[0])
            self.current_folder = self.saved_folders[0]
            self.settings.set("output_folder", self.current_folder)

    # ---- Кнопки помощи ----
    def _create_help_button(self, key):
        btn = QPushButton("?")
        btn.setFixedSize(28, 28)
        accent = self.settings.get("accent_color", "#7c4dff")
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #444444;
                border-radius: 4px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {accent};
                color: white;
            }}
        """)
        btn.clicked.connect(lambda: self.help_callback(key))
        return btn

    # ---- Синхронизация UI с настройками ----
    def sync_ui_from_settings(self):
        # Обновляем все QComboBox
        for widget in self.findChildren(QComboBox):
            obj_name = widget.objectName()
            if obj_name:
                val = self.settings.get(obj_name)
                if val is not None:
                    widget.setCurrentText(str(val))
        # Обновляем все QCheckBox
        for widget in self.findChildren(QCheckBox):
            obj_name = widget.objectName()
            if obj_name:
                val = self.settings.get(obj_name)
                if val is not None:
                    widget.setChecked(val)
        # Обновляем все QLineEdit
        for widget in self.findChildren(QLineEdit):
            obj_name = widget.objectName()
            if obj_name:
                val = self.settings.get(obj_name)
                if val is not None:
                    widget.setText(str(val))
        # Обновляем все SpinBoxEx
        for widget in self.findChildren(SpinBoxEx):
            obj_name = widget.objectName()
            if obj_name:
                val = self.settings.get(obj_name)
                if val is not None:
                    widget.setValue(val)
        # Обновляем папки
        self.saved_folders = self.settings.get("saved_folders", [])
        self.current_folder = self.settings.get("output_folder", "")
        self._update_folder_combo()

    # ---- Обновление стиля при смене цвета ----
    def update_accent_color(self):
        accent = self.settings.get("accent_color", "#7c4dff")
        for child in self.findChildren(QPushButton):
            if child.text() == "?":
                child.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #2a2a2a;
                        color: #e0e0e0;
                        border: 1px solid #444444;
                        border-radius: 4px;
                        font-size: 10pt;
                    }}
                    QPushButton:hover {{
                        background-color: {accent};
                        color: white;
                    }}
                """)
        for spin in self.findChildren(SpinBoxEx):
            spin.update_accent_color(accent)
