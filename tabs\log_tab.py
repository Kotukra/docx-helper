# tabs/log_tab.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QApplication, QMessageBox
)

class LogTab(QWidget):
    def __init__(self, settings_manager, help_callback):
        super().__init__()
        self.settings = settings_manager
        self.help_callback = help_callback

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        log_controls = QHBoxLayout()
        btn_copy = QPushButton("📋 Копировать лог")
        btn_copy.clicked.connect(self.copy_log)
        hbox_copy = QHBoxLayout()
        hbox_copy.addWidget(btn_copy)
        hbox_copy.addWidget(self._create_help_button("copy_log"))
        log_controls.addLayout(hbox_copy)

        btn_clear_log = QPushButton("🗑 Очистить лог")
        btn_clear_log.clicked.connect(self.clear_log)
        hbox_clear = QHBoxLayout()
        hbox_clear.addWidget(btn_clear_log)
        hbox_clear.addWidget(self._create_help_button("clear_log"))
        log_controls.addLayout(hbox_clear)

        layout.addLayout(log_controls)

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

    def copy_log(self):
        text = self.log_text.toPlainText()
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "Копирование", "Лог скопирован в буфер обмена")

    def clear_log(self):
        self.log_text.clear()

    def append_log(self, text):
        self.log_text.append(text)

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