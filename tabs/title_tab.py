import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QComboBox, QCheckBox, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt

class TitleTab(QWidget):
    def __init__(self, settings_manager, help_callback):
        super().__init__()
        self.settings = settings_manager
        self.help_callback = help_callback

        # Путь относительно файла приложения, а не текущей рабочей папки:
        # запуск через ярлык/другой каталог не должен ломать поиск шаблонов.
        self.templates_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tit")
        self.templates_list = []          # список кортежей (key, path, enabled)
        self.title_mode = "cyclic"
        self.order_keys_list = []

        self._build_ui()
        self.sync_ui_from_settings()
        self.scan_templates()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        hbox_title = QHBoxLayout()
        self.cb_title = QCheckBox("Включить титульные листы")
        self.cb_title.setObjectName("title_enabled")
        self.cb_title.setChecked(self.settings.get("title_enabled", False))
        self.cb_title.stateChanged.connect(lambda s: self.settings.set("title_enabled", s == Qt.Checked))
        hbox_title.addWidget(self.cb_title)
        hbox_title.addWidget(self._create_help_button("title_enabled"))
        layout.addLayout(hbox_title)

        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("Папка шаблонов:"))
        self.templates_folder_edit = QLineEdit(self.templates_folder)
        self.templates_folder_edit.textChanged.connect(self.on_templates_folder_changed)
        hbox.addWidget(self.templates_folder_edit)
        hbox.addWidget(self._create_help_button("templates_folder"))
        btn_browse = QPushButton("Обзор")
        btn_browse.clicked.connect(self.choose_templates_folder)
        hbox.addWidget(btn_browse)
        btn_scan = QPushButton("Обновить")
        btn_scan.clicked.connect(self.scan_templates)
        hbox.addWidget(btn_scan)
        hbox.addWidget(self._create_help_button("scan_templates"))
        layout.addLayout(hbox)

        self.templates_list_widget = QListWidget()
        self.templates_list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.templates_list_widget.itemChanged.connect(self._on_template_item_changed)
        layout.addWidget(QLabel("Шаблоны (ключ → файл):"))
        layout.addWidget(self.templates_list_widget)

        g = QGroupBox("Режим использования")
        g_layout = QVBoxLayout(g)
        self.single_radio = QCheckBox("Один для всех")
        self.cyclic_radio = QCheckBox("Циклическое чередование")
        self.single_radio.toggled.connect(self.on_title_mode_changed)
        self.cyclic_radio.toggled.connect(self.on_title_mode_changed)
        g_layout.addWidget(self.single_radio)
        g_layout.addWidget(self.cyclic_radio)

        hbox_single = QHBoxLayout()
        self.single_combo = QComboBox()
        hbox_single.addWidget(self.single_combo)
        hbox_single.addWidget(self._create_help_button("title_single_template"))
        g_layout.addLayout(hbox_single)

        hbox_order = QHBoxLayout()
        self.order_list = QListWidget()
        hbox_order.addWidget(self.order_list)
        hbox_order.addWidget(self._create_help_button("title_order"))
        g_layout.addLayout(hbox_order)

        btn_frame = QHBoxLayout()
        btn_up = QPushButton("↑ Вверх")
        btn_up.clicked.connect(self.move_up_order)
        btn_down = QPushButton("↓ Вниз")
        btn_down.clicked.connect(self.move_down_order)
        btn_fill = QPushButton("Заполнить")
        btn_fill.clicked.connect(self.fill_order_from_enabled)
        btn_frame.addWidget(btn_up)
        btn_frame.addWidget(btn_down)
        btn_frame.addWidget(btn_fill)
        g_layout.addLayout(btn_frame)
        layout.addWidget(g)

        self.title_mode = "cyclic"
        self.single_radio.setChecked(False)
        self.cyclic_radio.setChecked(True)
        self.on_title_mode_changed()

    def choose_templates_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с шаблонами")
        if folder:
            self.templates_folder_edit.setText(folder)
            self.scan_templates()

    def on_templates_folder_changed(self, text):
        self.templates_folder = text
        self.scan_templates()

    def scan_templates(self):
        folder = self.templates_folder_edit.text().strip()
        self.templates_list_widget.blockSignals(True)
        self.templates_list_widget.clear()
        self.templates_list = []
        if not folder or not os.path.isdir(folder):
            self.templates_list_widget.blockSignals(False)
            self._update_single_combo()
            self.fill_order_from_enabled()
            return
        for fname in sorted(os.listdir(folder), key=str.casefold):
            if fname.lower().endswith('.docx'):
                path = os.path.join(folder, fname)
                key = os.path.splitext(fname)[0]
                self.templates_list.append((key, path, True))
                item = QListWidgetItem(f"{key} -> {fname}")
                item.setCheckState(Qt.Checked)
                self.templates_list_widget.addItem(item)
        self.templates_list_widget.blockSignals(False)
        self._update_single_combo()
        self.fill_order_from_enabled()

    def _enabled_template_keys(self):
        return [self.templates_list_widget.item(i).text().split(" -> ", 1)[0]
                for i in range(self.templates_list_widget.count())
                if self.templates_list_widget.item(i).checkState() == Qt.Checked]

    def _on_template_item_changed(self, _item):
        """Синхронизирует доступные шаблоны с режимом одного/циклического титула."""
        enabled = self._enabled_template_keys()
        current_single = self.single_combo.currentText()
        self.single_combo.blockSignals(True)
        self.single_combo.clear()
        self.single_combo.addItems(enabled)
        if current_single in enabled:
            self.single_combo.setCurrentText(current_single)
        self.single_combo.blockSignals(False)

        # Сохраняем пользовательский порядок, но исключаем отключённые шаблоны.
        old_order = self.order_keys_list or [self.order_list.item(i).text()
                                             for i in range(self.order_list.count())]
        self.order_keys_list = [key for key in old_order if key in enabled]
        self.order_list.clear()
        self.order_list.addItems(self.order_keys_list)
        if not self.order_keys_list and enabled:
            self.fill_order_from_enabled()

    def _update_single_combo(self):
        self.single_combo.clear()
        for key, _, enabled in self.templates_list:
            if enabled:
                self.single_combo.addItem(key)
        if self.single_combo.count() > 0:
            self.single_combo.setCurrentIndex(0)

    def fill_order_from_enabled(self):
        self.order_list.clear()
        for key, _, enabled in self.templates_list:
            if enabled:
                self.order_list.addItem(key)
        self.order_keys_list = [self.order_list.item(i).text() for i in range(self.order_list.count())]

    def move_up_order(self):
        row = self.order_list.currentRow()
        if row > 0:
            item = self.order_list.takeItem(row)
            self.order_list.insertItem(row-1, item)
            self.order_list.setCurrentRow(row-1)
            self.order_keys_list = [self.order_list.item(i).text() for i in range(self.order_list.count())]

    def move_down_order(self):
        row = self.order_list.currentRow()
        if row < self.order_list.count() - 1:
            item = self.order_list.takeItem(row)
            self.order_list.insertItem(row+1, item)
            self.order_list.setCurrentRow(row+1)
            self.order_keys_list = [self.order_list.item(i).text() for i in range(self.order_list.count())]

    def on_title_mode_changed(self):
        if self.single_radio.isChecked():
            self.title_mode = "single"
            self.single_combo.setEnabled(True)
            self.order_list.setEnabled(False)
        else:
            self.title_mode = "cyclic"
            self.single_combo.setEnabled(False)
            self.order_list.setEnabled(True)

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
        self.cb_title.setChecked(self.settings.get("title_enabled", False))
        # Также обновляем список шаблонов, если надо
        self.scan_templates()

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

    def get_title_data(self):
        """Возвращает данные о титульных листах для сохранения в настройки."""
        templates = {}
        for i in range(self.templates_list_widget.count()):
            item = self.templates_list_widget.item(i)
            if item.checkState() == Qt.Checked:
                key = item.text().split(" -> ")[0]
                path = os.path.join(self.templates_folder_edit.text().strip(), key + ".docx")
                templates[key] = path
        return {
            "enabled": self.settings.get("title_enabled", False),
            "templates_folder": self.templates_folder_edit.text().strip(),
            "templates": templates,
            "per_part": self.order_keys_list if self.title_mode == "cyclic" else self.single_combo.currentText(),
            "title_mode": self.title_mode,
            "single_title_key": self.single_combo.currentText() if self.title_mode == "single" else "",
            "order_keys": self.order_keys_list
        }

    def apply_title_data(self, data):
        """Применяет данные о титульных листах из словаря."""
        self.settings.set("title_enabled", data.get("enabled", False))
        saved_folder = data.get("templates_folder")
        if saved_folder:
            self.templates_folder_edit.setText(saved_folder)
        self.sync_ui_from_settings()
        if "templates" in data:
            for i in range(self.templates_list_widget.count()):
                item = self.templates_list_widget.item(i)
                key = item.text().split(" -> ")[0]
                if key in data["templates"]:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
        mode = data.get("title_mode", "cyclic")
        if mode == "single":
            self.single_radio.setChecked(True)
            self.single_combo.setCurrentText(data.get("single_title_key", ""))
        else:
            self.cyclic_radio.setChecked(True)
            self.order_keys_list = data.get("order_keys", [])
            self._update_order_list()
        self.on_title_mode_changed()

    def _update_order_list(self):
        self.order_list.clear()
        for key in self.order_keys_list:
            self.order_list.addItem(key)