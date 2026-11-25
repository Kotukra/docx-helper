from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QComboBox, QCheckBox, QPushButton
)
from PySide6.QtCore import Qt

from widgets import SpinBoxEx

class ExtraTab(QWidget):
    def __init__(self, settings_manager, help_callback, spellcheck_langs):
        super().__init__()
        self.settings = settings_manager
        self.help_callback = help_callback
        self.spellcheck_langs = spellcheck_langs

        self._build_ui()
        self.sync_ui_from_settings()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- Очистка и форматирование ----
        g = QGroupBox("Очистка и форматирование")
        g_layout = QVBoxLayout(g)
        hbox_clean = QHBoxLayout()
        self.cb_clean = QCheckBox("Улучшенная очистка (HTML, типографика)")
        self.cb_clean.setObjectName("enhanced_cleaning")
        self.cb_clean.setChecked(self.settings.get("enhanced_cleaning", True))
        self.cb_clean.stateChanged.connect(lambda s: self.settings.set("enhanced_cleaning", s == Qt.Checked))
        hbox_clean.addWidget(self.cb_clean)
        hbox_clean.addWidget(self._create_help_button("enhanced_cleaning"))
        g_layout.addLayout(hbox_clean)

        hbox_md = QHBoxLayout()
        self.cb_md = QCheckBox("Режим Markdown")
        self.cb_md.setObjectName("markdown_mode")
        self.cb_md.setChecked(self.settings.get("markdown_mode", False))
        self.cb_md.stateChanged.connect(lambda s: self.settings.set("markdown_mode", s == Qt.Checked))
        hbox_md.addWidget(self.cb_md)
        hbox_md.addWidget(self._create_help_button("markdown_mode"))
        g_layout.addLayout(hbox_md)
        layout.addWidget(g)

        # ---- Именование файлов ----
        g = QGroupBox("Именование файлов")
        g_layout = QVBoxLayout(g)

        hbox_kw = QHBoxLayout()
        self.cb_kw = QCheckBox("Ключевые слова {keywords}")
        self.cb_kw.setObjectName("filename_use_keywords")
        self.cb_kw.setChecked(self.settings.get("filename_use_keywords", True))
        self.cb_kw.stateChanged.connect(lambda s: self.settings.set("filename_use_keywords", s == Qt.Checked))
        hbox_kw.addWidget(self.cb_kw)
        hbox_kw.addWidget(self._create_help_button("filename_use_keywords"))
        g_layout.addLayout(hbox_kw)

        hbox_date = QHBoxLayout()
        self.cb_date = QCheckBox("Дата {date}")
        self.cb_date.setObjectName("filename_use_date")
        self.cb_date.setChecked(self.settings.get("filename_use_date", True))
        self.cb_date.stateChanged.connect(lambda s: self.settings.set("filename_use_date", s == Qt.Checked))
        hbox_date.addWidget(self.cb_date)
        hbox_date.addWidget(self._create_help_button("filename_use_date"))
        g_layout.addLayout(hbox_date)

        hbox_time = QHBoxLayout()
        self.cb_time = QCheckBox("Время {time}")
        self.cb_time.setObjectName("filename_use_time")
        self.cb_time.setChecked(self.settings.get("filename_use_time", False))
        self.cb_time.stateChanged.connect(lambda s: self.settings.set("filename_use_time", s == Qt.Checked))
        hbox_time.addWidget(self.cb_time)
        hbox_time.addWidget(self._create_help_button("filename_use_time"))
        g_layout.addLayout(hbox_time)

        hbox_part = QHBoxLayout()
        self.cb_part = QCheckBox("Номер части {part}")
        self.cb_part.setObjectName("filename_use_part")
        self.cb_part.setChecked(self.settings.get("filename_use_part", False))
        self.cb_part.stateChanged.connect(lambda s: self.settings.set("filename_use_part", s == Qt.Checked))
        hbox_part.addWidget(self.cb_part)
        hbox_part.addWidget(self._create_help_button("filename_use_part"))
        g_layout.addLayout(hbox_part)

        hbox_sep = QHBoxLayout()
        hbox_sep.addWidget(QLabel("Разделитель:"))
        self.sep_edit = QLineEdit(self.settings.get("filename_separator", "_"))
        self.sep_edit.setObjectName("filename_separator")
        self.sep_edit.textChanged.connect(lambda v: self.settings.set("filename_separator", v))
        hbox_sep.addWidget(self.sep_edit)
        hbox_sep.addWidget(self._create_help_button("filename_separator"))
        g_layout.addLayout(hbox_sep)

        hbox_topn = QHBoxLayout()
        hbox_topn.addWidget(QLabel("Кол-во ключевых слов:"))
        self.spin_topn = SpinBoxEx(1, 10, 1, 0, self.settings.get("naming_top_n", 4))
        self.spin_topn.setObjectName("naming_top_n")
        self.spin_topn.valueChanged.connect(lambda v: self.settings.set("naming_top_n", v))
        hbox_topn.addWidget(self.spin_topn)
        hbox_topn.addWidget(self._create_help_button("naming_top_n"))
        g_layout.addLayout(hbox_topn)

        hbox_ask = QHBoxLayout()
        self.cb_ask = QCheckBox("Спрашивать имя перед сохранением")
        self.cb_ask.setObjectName("ask_filename")
        self.cb_ask.setChecked(self.settings.get("ask_filename", False))
        self.cb_ask.stateChanged.connect(lambda s: self.settings.set("ask_filename", s == Qt.Checked))
        hbox_ask.addWidget(self.cb_ask)
        hbox_ask.addWidget(self._create_help_button("ask_filename"))
        g_layout.addLayout(hbox_ask)
        layout.addWidget(g)

        # ---- Орфография ----
        g = QGroupBox("Орфография")
        g_layout = QHBoxLayout(g)
        g_layout.addWidget(QLabel("Язык:"))
        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName("spellcheck_lang")
        self.lang_combo.addItems(self.spellcheck_langs)
        self.lang_combo.setCurrentText(self.settings.get("spellcheck_lang", "ru"))
        self.lang_combo.currentTextChanged.connect(lambda v: self.settings.set("spellcheck_lang", v))
        g_layout.addWidget(self.lang_combo)
        g_layout.addWidget(self._create_help_button("spellcheck_lang"))
        layout.addWidget(g)

        # ---- Прочее ----
        g = QGroupBox("Прочее")
        g_layout = QVBoxLayout(g)
        hbox_detect = QHBoxLayout()
        self.cb_detect = QCheckBox("Проверять проблемы в тексте")
        self.cb_detect.setObjectName("detect_issues")
        self.cb_detect.setChecked(self.settings.get("detect_issues", True))
        self.cb_detect.stateChanged.connect(lambda s: self.settings.set("detect_issues", s == Qt.Checked))
        hbox_detect.addWidget(self.cb_detect)
        hbox_detect.addWidget(self._create_help_button("detect_issues"))
        g_layout.addLayout(hbox_detect)
        layout.addWidget(g)

        layout.addStretch()

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

    def sync_ui_from_settings(self):
        for widget in self.findChildren(QCheckBox):
            obj_name = widget.objectName()
            if obj_name:
                val = self.settings.get(obj_name)
                if val is not None:
                    widget.setChecked(val)
        for widget in self.findChildren(QLineEdit):
            obj_name = widget.objectName()
            if obj_name:
                val = self.settings.get(obj_name)
                if val is not None:
                    widget.setText(str(val))
        for widget in self.findChildren(QComboBox):
            obj_name = widget.objectName()
            if obj_name:
                val = self.settings.get(obj_name)
                if val is not None:
                    widget.setCurrentText(str(val))
        for widget in self.findChildren(SpinBoxEx):
            obj_name = widget.objectName()
            if obj_name:
                val = self.settings.get(obj_name)
                if val is not None:
                    widget.setValue(val)

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