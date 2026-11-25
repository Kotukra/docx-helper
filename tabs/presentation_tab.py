# tabs/presentation_tab.py
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QCheckBox, QPushButton, QFileDialog, QListWidget, QListWidgetItem,
    QMessageBox, QSpinBox, QGridLayout
)
from PySide6.QtCore import Qt
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from widgets import SpinBoxEx, HelpWindow


class PresentationTab(QWidget):
    def __init__(self, settings_manager, help_callback, parent_window=None):
        super().__init__()
        self.settings = settings_manager
        self.help_callback = help_callback
        self.parent_window = parent_window
        self._build_ui()
        self.sync_ui_from_settings()

    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ================= Шаблон =================
        g = QGroupBox("Шаблон презентации (.pptx)")
        gl = QVBoxLayout(g)

        h = QHBoxLayout()
        h.addWidget(QLabel("Папка:"))
        self.folder_edit = QLineEdit(self.settings.get("ppt_template_folder", "templates_ppt"))
        self.folder_edit.textChanged.connect(self._on_folder_changed)
        h.addWidget(self.folder_edit)
        btn_browse = QPushButton("📁 Обзор")
        btn_browse.clicked.connect(self._choose_folder)
        h.addWidget(btn_browse)
        btn_scan = QPushButton("🔄 Обновить")
        btn_scan.clicked.connect(self.scan_templates)
        h.addWidget(btn_scan)
        gl.addLayout(h)

        gl.addWidget(QLabel("Найденные .pptx:"))
        self.templates_list = QListWidget()
        self.templates_list.itemSelectionChanged.connect(self._on_template_selected)
        gl.addWidget(self.templates_list)

        library_actions = QHBoxLayout()
        btn_preview_template = QPushButton("Предпросмотр выбранного шаблона")
        btn_preview_template.clicked.connect(self.preview_selected_template)
        library_actions.addWidget(btn_preview_template)
        btn_open_template_folder = QPushButton("Открыть папку библиотеки")
        btn_open_template_folder.clicked.connect(self.open_template_folder)
        library_actions.addWidget(btn_open_template_folder)
        gl.addLayout(library_actions)

        h = QHBoxLayout()
        btn_make_starter = QPushButton("➕ Создать шаблон-заготовку")
        btn_make_starter.setToolTip(
            "Создаст starter.pptx со стандартными layout-ами, "
            "если у вас ещё нет своего шаблона"
        )
        btn_make_starter.clicked.connect(self._make_starter_template)
        h.addWidget(btn_make_starter)
        btn_import_docx = QPushButton("Создать слайды из DOCX…")
        btn_import_docx.clicked.connect(self._import_docx)
        h.addWidget(btn_import_docx)
        btn_edit_slides = QPushButton("Редактировать слайды…")
        btn_edit_slides.clicked.connect(self._edit_slides)
        h.addWidget(btn_edit_slides)
        gl.addLayout(h)

        layout.addWidget(g)

        # ================= Шрифты и лимиты =================
        g = QGroupBox("Шрифты и лимиты")
        gl = QVBoxLayout(g)

        row = QHBoxLayout()
        row.addWidget(QLabel("Размер пунктов:"))
        self.spin_size = SpinBoxEx(12, 48, 2, 0, self.settings.get("ppt_bullet_size", 28))
        self.spin_size.valueChanged.connect(lambda v: self.settings.set("ppt_bullet_size", int(v)))
        row.addWidget(self.spin_size)
        row.addStretch()
        gl.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Минимальный размер:"))
        self.spin_min = SpinBoxEx(10, 32, 1, 0, self.settings.get("ppt_bullet_min_size", 14))
        self.spin_min.valueChanged.connect(lambda v: self.settings.set("ppt_bullet_min_size", int(v)))
        row.addWidget(self.spin_min)
        row.addStretch()
        gl.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Макс. пунктов на слайд:"))
        self.spin_max = SpinBoxEx(3, 20, 1, 0, self.settings.get("ppt_max_items", 8))
        self.spin_max.valueChanged.connect(lambda v: self.settings.set("ppt_max_items", int(v)))
        row.addWidget(self.spin_max)
        row.addStretch()
        gl.addLayout(row)

        self.cb_notes = QCheckBox("Сохранять спикерские заметки (NOTES)")
        self.cb_notes.setChecked(self.settings.get("ppt_keep_notes", True))
        self.cb_notes.stateChanged.connect(
            lambda s: self.settings.set("ppt_keep_notes", s == Qt.Checked)
        )
        gl.addWidget(self.cb_notes)

        self.cb_slide_numbers = QCheckBox("Добавлять номера слайдов")
        self.cb_slide_numbers.setChecked(bool(self.settings.get("ppt_slide_numbers", False)))
        self.cb_slide_numbers.stateChanged.connect(
            lambda s: self.settings.set("ppt_slide_numbers", s == Qt.Checked)
        )
        gl.addWidget(self.cb_slide_numbers)

        layout.addWidget(g)

        # ================= Готовый шаблон (слайды-образцы) =================
        g = QGroupBox("Готовый шаблон (SlidesMania / Slidesgo и т.п.)")
        gl = QVBoxLayout(g)

        self.cb_clone = QCheckBox("Использовать слайды-образцы из шаблона")
        self.cb_clone.setChecked(bool(self.settings.get("ppt_use_clone_mode", False)))
        self.cb_clone.stateChanged.connect(self._on_clone_toggled)
        gl.addWidget(self.cb_clone)

        hint = QLabel(
            "Если шаблон — это готовая презентация с собственным дизайном, "
            "layout-ы в нём нестандартные. Укажите номер слайда для каждого типа: "
            "приложение склонирует этот слайд и заменит в нём текст.\n\n"
            "Откройте шаблон в PowerPoint и посмотрите номера страниц."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 9pt;")
        gl.addWidget(hint)

        clone_defaults = {
            "title": 1,
            "section": 4,
            "bullets": 8,
            "image_right": 5,
            "image_full": 2,
            "table": 12,
            "chart": 14,
            "conclusion": 21,
        }
        clone_labels = {
            "title": "Титульный",
            "section": "Раздел",
            "bullets": "Список",
            "image_right": "Картинка справа",
            "image_full": "Картинка на весь слайд",
            "table": "Таблица",
            "chart": "График",
            "conclusion": "Финал",
        }
        clone_map = self.settings.get("ppt_clone_map", {}) or {}

        grid = QGridLayout()
        row_idx = 0
        self.clone_spins = {}
        for stype, label in clone_labels.items():
            grid.addWidget(QLabel(label), row_idx, 0)
            spin = QSpinBox()
            spin.setRange(1, 500)
            try:
                default_val = int(clone_map.get(stype, clone_defaults[stype]))
            except Exception:
                default_val = clone_defaults[stype]
            spin.setValue(default_val)
            spin.setEnabled(self.cb_clone.isChecked())
            spin.valueChanged.connect(
                lambda v, t=stype: self._on_clone_map_changed(t, v)
            )
            grid.addWidget(spin, row_idx, 1)
            self.clone_spins[stype] = spin
            row_idx += 1
        gl.addLayout(grid)

        layout.addWidget(g)

        # ================= Справка =================
        btn_help = QPushButton("❓ Как размечать слайды для ИИ")
        btn_help.clicked.connect(self.show_help_markup)
        layout.addWidget(btn_help)

        layout.addStretch()
        self.scan_templates()

    # ------------------------------------------------------------------
    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Папка с шаблонами .pptx")
        if folder:
            self.folder_edit.setText(folder)
            self.scan_templates()

    def _on_folder_changed(self, text):
        self.settings.set("ppt_template_folder", text.strip())
        self.scan_templates()

    def scan_templates(self):
        folder = self.folder_edit.text().strip()
        self.templates_list.clear()
        if not folder or not os.path.isdir(folder):
            return
        current = self.settings.get("ppt_template_path", "")
        for fname in sorted(os.listdir(folder)):
            if not fname.lower().endswith(".pptx"):
                continue
            path = os.path.join(folder, fname)
            item = QListWidgetItem(fname)
            item.setData(Qt.UserRole, path)
            self.templates_list.addItem(item)
            if os.path.normpath(path) == os.path.normpath(current or ""):
                item.setSelected(True)

    def _on_template_selected(self):
        items = self.templates_list.selectedItems()
        if items:
            path = items[0].data(Qt.UserRole)
            self.settings.set("ppt_template_path", path)

    def preview_selected_template(self):
        items = self.templates_list.selectedItems()
        path = items[0].data(Qt.UserRole) if items else self.settings.get("ppt_template_path", "")
        if not path or not os.path.isfile(path):
            QMessageBox.information(self, "Предпросмотр шаблона", "Сначала выберите существующий PPTX-шаблон.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            QMessageBox.warning(self, "Предпросмотр шаблона", "Windows не смогла открыть выбранный файл.")

    def open_template_folder(self):
        folder = os.path.abspath(self.folder_edit.text().strip() or "templates_ppt")
        os.makedirs(folder, exist_ok=True)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(folder)):
            QMessageBox.warning(self, "Библиотека шаблонов", f"Не удалось открыть папку:\n{folder}")

    def _make_starter_template(self):
        folder = self.folder_edit.text().strip() or "templates_ppt"
        try:
            from make_starter_template import make_starter_template
            path = make_starter_template(folder)
            QMessageBox.information(self, "Готово", f"Шаблон создан:\n{path}")
            self.scan_templates()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать шаблон:\n{e}")

    def _import_docx(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите документ Word", "", "Word (*.docx)")
        if not path:
            return
        try:
            if self.parent_window and hasattr(self.parent_window, "import_docx_to_presentation"):
                self.parent_window.import_docx_to_presentation(path)
        except Exception as exc:
            QMessageBox.warning(self, "Создание слайдов", f"Не удалось прочитать DOCX:\n{exc}")

    def _edit_slides(self):
        if self.parent_window and hasattr(self.parent_window, "edit_presentation_slides"):
            self.parent_window.edit_presentation_slides()

    # ------------------------------------------------------------------
    def _on_clone_toggled(self, state):
        enabled = state == Qt.Checked
        self.settings.set("ppt_use_clone_mode", enabled)
        for spin in getattr(self, "clone_spins", {}).values():
            spin.setEnabled(enabled)

    def _on_clone_map_changed(self, stype, value):
        m = dict(self.settings.get("ppt_clone_map", {}) or {})
        m[stype] = int(value)
        self.settings.set("ppt_clone_map", m)

    # ------------------------------------------------------------------
    def show_help_markup(self):
        text = (
            "<b>Разметка слайдов для нейросети</b><br><br>"
            "Слайды разделяются строкой <code>---</code>.<br>"
            "Каждый слайд начинается с маркера типа:<br><br>"
            "<code>[SLIDE: title]</code> — титульный слайд<br>"
            "<code>[SLIDE: bullets]</code> — заголовок + маркированный список<br>"
            "<code>[SLIDE: image_right]</code> — картинка справа, список слева<br>"
            "<code>[SLIDE: image_left]</code> — картинка слева, список справа<br>"
            "<code>[SLIDE: image_full]</code> — картинка на весь слайд<br>"
            "<code>[SLIDE: chart]</code> — график<br>"
            "<code>[SLIDE: table]</code> — таблица<br>"
            "<code>[SLIDE: section]</code> — разделитель раздела<br>"
            "<code>[SLIDE: conclusion]</code> — финальный слайд<br><br>"
            "<b>Заголовок:</b> строка после <code>[SLIDE: …]</code>, начинающаяся с <code># </code><br>"
            "<b>Подзаголовок</b> (для title/conclusion): <code>[SUB: текст]</code><br>"
            "<b>Пункты:</b> <code>- текст</code>; вложенные — с отступом в 2 пробела<br>"
            "<b>Картинка:</b> <code>[IMAGE: путь/к/картинке.png]</code> "
            "или описание, если файла пока нет<br>"
            "<b>Спикерские заметки:</b> <code>[NOTES: текст доклада]</code><br>"
            "<b>График:</b><br>"
            "<code>[CHART: bar]</code><br>"
            "2020: 12000<br>2021: 15000<br><code>[/CHART]</code><br>"
            "(типы: bar, line, pie, col)<br>"
            "<b>Таблица:</b> markdown-таблица внутри <code>[TABLE]…[/TABLE]</code><br><br>"
            "<i>Лимиты:</i> на слайде до 8 пунктов, в пункте — до 120 символов. "
            "Если больше — шрифт уменьшается автоматически."
        )
        win = HelpWindow(text, self)
        win.setWindowTitle("Разметка презентации")
        win.resize(720, 560)
        win.show()

    # ------------------------------------------------------------------
    def sync_ui_from_settings(self):
        self.spin_size.setValue(self.settings.get("ppt_bullet_size", 28))
        self.spin_min.setValue(self.settings.get("ppt_bullet_min_size", 14))
        self.spin_max.setValue(self.settings.get("ppt_max_items", 8))
        self.cb_notes.setChecked(bool(self.settings.get("ppt_keep_notes", True)))
        self.cb_slide_numbers.setChecked(bool(self.settings.get("ppt_slide_numbers", False)))

        use_clone = bool(self.settings.get("ppt_use_clone_mode", False))
        if hasattr(self, "cb_clone"):
            self.cb_clone.setChecked(use_clone)
        clone_map = self.settings.get("ppt_clone_map", {}) or {}
        for stype, spin in getattr(self, "clone_spins", {}).items():
            try:
                spin.setValue(int(clone_map.get(stype, spin.value())))
            except Exception:
                pass
            spin.setEnabled(use_clone)

        self.folder_edit.setText(self.settings.get("ppt_template_folder", "templates_ppt"))
        self.scan_templates()

    def update_accent_color(self):
        accent = self.settings.get("accent_color", "#7c4dff")
        for btn in self.findChildren(QPushButton):
            if btn.text() == "?":
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #2a2a2a; color: #e0e0e0;
                        border: 1px solid #444; border-radius: 4px;
                        font-size: 10pt;
                    }}
                    QPushButton:hover {{ background-color: {accent}; color: white; }}
                """)

    # ------------------------------------------------------------------
    def get_presentation_data(self):
        clone_map = dict(self.settings.get("ppt_clone_map", {}) or {})
        if hasattr(self, "clone_spins"):
            for stype, spin in self.clone_spins.items():
                clone_map[stype] = int(spin.value())
        return {
            "template_folder": self.folder_edit.text().strip(),
            "template_path": self.settings.get("ppt_template_path", ""),
            "bullet_size": int(self.spin_size.value()),
            "bullet_min_size": int(self.spin_min.value()),
            "max_items": int(self.spin_max.value()),
            "keep_notes": bool(self.settings.get("ppt_keep_notes", True)),
            "use_clone_mode": bool(self.settings.get("ppt_use_clone_mode", False)),
            "clone_map": clone_map,
        }

    def apply_presentation_data(self, data):
        if "template_folder" in data:
            self.folder_edit.setText(data["template_folder"])
        mapping = {
            "ppt_template_path": "template_path",
            "ppt_bullet_size": "bullet_size",
            "ppt_bullet_min_size": "bullet_min_size",
            "ppt_max_items": "max_items",
            "ppt_keep_notes": "keep_notes",
            "ppt_use_clone_mode": "use_clone_mode",
            "ppt_clone_map": "clone_map",
        }
        for key, src in mapping.items():
            if src in data:
                self.settings.set(key, data[src])
        self.sync_ui_from_settings()
