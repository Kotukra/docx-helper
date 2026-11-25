"""Basic list-based slide editor dialog; generated elements remain in the model."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QLineEdit, QPlainTextEdit,
    QComboBox, QPushButton, QLabel, QMessageBox, QDialogButtonBox,
)

from processor.ppt_creator import parse_presentation
from slide_editor import SLIDE_TYPES, serialize_presentation


class SlideEditorDialog(QDialog):
    def __init__(self, parent=None, markup=""):
        super().__init__(parent)
        self.setWindowTitle("Редактор слайдов")
        self.resize(840, 560)
        self.slides = parse_presentation(markup)
        if not self.slides:
            self.slides = [{"type": "bullets", "title": "Новый слайд", "subtitle": "",
                            "bullets": [], "notes": "", "images": [], "chart": None, "table": None}]
        root = QVBoxLayout(self)
        body = QHBoxLayout()
        self.slide_list = QListWidget()
        body.addWidget(self.slide_list, 1)
        editor = QVBoxLayout()
        editor.addWidget(QLabel("Заголовок"))
        self.title_edit = QLineEdit()
        editor.addWidget(self.title_edit)
        editor.addWidget(QLabel("Тип слайда"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(SLIDE_TYPES)
        editor.addWidget(self.type_combo)
        editor.addWidget(QLabel("Пункты (каждый с новой строки)"))
        self.bullets_edit = QPlainTextEdit()
        editor.addWidget(self.bullets_edit, 1)
        body.addLayout(editor, 2)
        root.addLayout(body, 1)

        actions = QHBoxLayout()
        for label, handler in (("Добавить", self.add_slide), ("Вверх", lambda: self.move_slide(-1)),
                               ("Вниз", lambda: self.move_slide(1)), ("Удалить", self.delete_slide)):
            button = QPushButton(label)
            button.clicked.connect(handler)
            actions.addWidget(button)
        root.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.slide_list.currentRowChanged.connect(self.load_slide)
        self._refresh_list(0)

    def _store_current(self):
        index = self.slide_list.currentRow()
        if not 0 <= index < len(self.slides):
            return
        slide = self.slides[index]
        slide["title"] = self.title_edit.text().strip()
        slide["type"] = self.type_combo.currentText()
        slide["bullets"] = []
        for line in self.bullets_edit.toPlainText().splitlines():
            if line.strip():
                spaces = len(line) - len(line.lstrip())
                slide["bullets"].append((spaces // 2, line.strip().lstrip("-*+ ")))

    def load_slide(self, index):
        if not 0 <= index < len(self.slides):
            return
        slide = self.slides[index]
        self.title_edit.setText(slide.get("title", ""))
        slide_type = slide.get("type", "bullets")
        if self.type_combo.findText(slide_type) < 0:
            self.type_combo.addItem(slide_type)
        self.type_combo.setCurrentText(slide_type)
        self.bullets_edit.setPlainText("\n".join("  " * level + text
                                               for level, text in slide.get("bullets", [])))

    def _refresh_list(self, select=0):
        self.slide_list.blockSignals(True)
        self.slide_list.clear()
        self.slide_list.addItems([f"{i + 1}. {slide.get('title') or 'Без заголовка'}"
                                  for i, slide in enumerate(self.slides)])
        self.slide_list.blockSignals(False)
        if self.slides:
            self.slide_list.setCurrentRow(max(0, min(select, len(self.slides) - 1)))

    def add_slide(self):
        self._store_current()
        self.slides.append({"type": "bullets", "title": "Новый слайд", "subtitle": "",
                            "bullets": [], "notes": "", "images": [], "chart": None, "table": None})
        self._refresh_list(len(self.slides) - 1)

    def move_slide(self, offset):
        self._store_current()
        index = self.slide_list.currentRow()
        target = index + offset
        if 0 <= index < len(self.slides) and 0 <= target < len(self.slides):
            self.slides[index], self.slides[target] = self.slides[target], self.slides[index]
            self._refresh_list(target)

    def delete_slide(self):
        self._store_current()
        index = self.slide_list.currentRow()
        if 0 <= index < len(self.slides):
            del self.slides[index]
            self._refresh_list(min(index, len(self.slides) - 1))

    def accept(self):
        self._store_current()
        if not self.slides:
            QMessageBox.warning(self, "Редактор слайдов", "Оставьте хотя бы один слайд.")
            return
        super().accept()

    def markup(self):
        return serialize_presentation(self.slides)
