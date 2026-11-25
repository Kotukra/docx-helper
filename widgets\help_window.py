# widgets/help_window.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton
from PySide6.QtCore import Qt

class HelpWindow(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Подсказка")
        self.setGeometry(200, 200, 500, 300)
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        btn = QPushButton("Закрыть")
        btn.clicked.connect(self.close)
        layout.addWidget(btn, alignment=Qt.AlignCenter)