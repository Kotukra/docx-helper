# widgets/spinbox_ex.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QSizePolicy
from PySide6.QtCore import Signal, Qt

class SpinBoxEx(QWidget):
    valueChanged = Signal(float)

    def __init__(self, min_val, max_val, step=1.0, decimals=0, initial=None, parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.decimals = decimals
        self._value = initial if initial is not None else min_val
        self._setup_ui()
        self.line_edit.setText(self._format_value(self._value))
        self.setValue(self._value)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.line_edit = QLineEdit()
        self.line_edit.setFixedWidth(80)
        self.line_edit.setFixedHeight(28)
        self.line_edit.setAlignment(Qt.AlignCenter)
        self.line_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.line_edit)

        self.minus_btn = QPushButton("−")
        self.minus_btn.setFixedSize(28, 28)
        self.minus_btn.clicked.connect(self._decrement)
        layout.addWidget(self.minus_btn)

        self.plus_btn = QPushButton("+")
        self.plus_btn.setFixedSize(28, 28)
        self.plus_btn.clicked.connect(self._increment)
        layout.addWidget(self.plus_btn)

        self._update_button_style()

    def _update_button_style(self, accent_color="#7c4dff"):
        style = f"""
            QPushButton {{
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #444444;
                border-radius: 4px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {accent_color};
                color: white;
            }}
        """
        self.minus_btn.setStyleSheet(style)
        self.plus_btn.setStyleSheet(style)

    def update_accent_color(self, accent_color):
        self._update_button_style(accent_color)

    def _increment(self):
        self.setValue(self._value + self.step)

    def _decrement(self):
        self.setValue(self._value - self.step)

    def _on_text_changed(self, text):
        try:
            val = float(text.replace(',', '.'))
            if self.min_val <= val <= self.max_val:
                self._value = val
                self.valueChanged.emit(self._value)
            else:
                self.line_edit.setText(self._format_value(self._value))
        except ValueError:
            pass

    def _format_value(self, val):
        if self.decimals == 0:
            return str(int(val))
        else:
            fmt = f"{{:.{self.decimals}f}}"
            return fmt.format(val)

    def setValue(self, val):
        val = max(self.min_val, min(self.max_val, val))
        if self._value != val:
            self._value = val
            self.line_edit.setText(self._format_value(val))
            self.valueChanged.emit(val)

    def value(self):
        return self._value