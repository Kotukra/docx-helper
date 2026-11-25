"""Small dialogs for inserting or editing Markdown tables and image markers."""
from pathlib import Path

from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox,
    QDoubleSpinBox, QTableWidget, QTableWidgetItem, QPushButton,
    QDialogButtonBox, QFileDialog,
    QComboBox,
)

from markdown_editors import build_markdown_table, build_image_marker


class TableEditorDialog(QDialog):
    def __init__(self, parent=None, rows=None, caption=""):
        super().__init__(parent)
        self.setWindowTitle("Редактор таблицы")
        self.resize(720, 460)
        rows = rows or [["Заголовок 1", "Заголовок 2"], ["", ""]]
        row_count, col_count = len(rows), max(map(len, rows))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Подпись таблицы (необязательно)"))
        self.caption_edit = QLineEdit(caption)
        layout.addWidget(self.caption_edit)

        dimensions = QHBoxLayout()
        dimensions.addWidget(QLabel("Строки"))
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 50)
        self.rows_spin.setValue(row_count)
        dimensions.addWidget(self.rows_spin)
        dimensions.addWidget(QLabel("Столбцы"))
        self.columns_spin = QSpinBox()
        self.columns_spin.setRange(1, 20)
        self.columns_spin.setValue(col_count)
        dimensions.addWidget(self.columns_spin)
        dimensions.addStretch()
        layout.addLayout(dimensions)

        self.table = QTableWidget(row_count, col_count)
        self.table.setHorizontalHeaderLabels([f"Столбец {index + 1}" for index in range(col_count)])
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                self.table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
        self.rows_spin.valueChanged.connect(self._resize_table)
        self.columns_spin.valueChanged.connect(self._resize_table)
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _resize_table(self):
        self.table.setRowCount(self.rows_spin.value())
        self.table.setColumnCount(self.columns_spin.value())
        self.table.setHorizontalHeaderLabels(
            [f"Столбец {index + 1}" for index in range(self.columns_spin.value())])

    def markdown(self):
        rows = []
        for row in range(self.table.rowCount()):
            rows.append([self.table.item(row, column).text() if self.table.item(row, column) else ""
                         for column in range(self.table.columnCount())])
        return build_markdown_table(rows, self.caption_edit.text())


class ImageEditorDialog(QDialog):
    def __init__(self, parent=None, path="", caption="", width_cm=15.0, alignment="center"):
        super().__init__(parent)
        self.setWindowTitle("Редактор изображения")
        self.resize(520, 420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Файл изображения"))
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(path)
        self.path_edit.textChanged.connect(self._update_preview)
        path_row.addWidget(self.path_edit, 1)
        browse = QPushButton("Выбрать…")
        browse.clicked.connect(self.choose_file)
        path_row.addWidget(browse)
        layout.addLayout(path_row)
        self.preview = QLabel("Предпросмотр")
        self.preview.setMinimumHeight(180)
        self.preview.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview, 1)
        layout.addWidget(QLabel("Подпись"))
        self.caption_edit = QLineEdit(caption)
        layout.addWidget(self.caption_edit)
        width_row = QHBoxLayout()
        width_row.addWidget(QLabel("Ширина при вставке (см)"))
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(2.0, 20.0)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setValue(float(width_cm))
        width_row.addWidget(self.width_spin)
        layout.addLayout(width_row)
        alignment_row = QHBoxLayout()
        alignment_row.addWidget(QLabel("Расположение"))
        self.alignment_combo = QComboBox()
        self.alignment_combo.addItem("По центру", "center")
        self.alignment_combo.addItem("Слева", "left")
        self.alignment_combo.addItem("Справа", "right")
        index = self.alignment_combo.findData(alignment)
        self.alignment_combo.setCurrentIndex(index if index >= 0 else 0)
        alignment_row.addWidget(self.alignment_combo)
        layout.addLayout(alignment_row)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._update_preview()

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение", "", "Изображения (*.png *.jpg *.jpeg *.gif *.bmp *.tif *.tiff)")
        if path:
            self.path_edit.setText(path)
            self._update_preview()

    def _update_preview(self):
        path = self.path_edit.text().strip()
        if not path or not Path(path).is_file():
            self.preview.setText("Выберите изображение для предпросмотра")
            self.preview.setPixmap(QPixmap())
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.preview.setText("Не удалось показать предпросмотр")
            return
        self.preview.setPixmap(pixmap.scaled(480, 190, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def image_marker(self):
        return build_image_marker(self.path_edit.text(), self.caption_edit.text(),
                                  self.width_spin.value(), self.alignment_combo.currentData())
