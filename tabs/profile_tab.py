# tabs/profile_tab.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QFileDialog, QMessageBox, QColorDialog, QCheckBox, QComboBox, QDialog, QPlainTextEdit, QInputDialog, QGridLayout,
    QLineEdit
)
from PySide6.QtCore import Qt
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor
import json
from document_profile_manager import list_profiles, get_profile, save_profile, delete_profile
from ui_theme import BUILTIN_PALETTES, DEFAULT_COLORS, normalize_colors, normalize_palettes
from favorite_presets import FavoritePresetManager
from update_checker import check_for_update


class UpdateCheckThread(QThread):
    finished_check = Signal(object, object)

    def __init__(self, url, version, parent=None):
        super().__init__(parent)
        self.url = url
        self.version = version

    def run(self):
        try:
            self.finished_check.emit(check_for_update(self.url, self.version), None)
        except Exception as exc:
            self.finished_check.emit(None, str(exc))

class ProfileTab(QWidget):
    def __init__(self, settings_manager, help_callback, parent_window=None):
        super().__init__()
        self.settings = settings_manager
        self.help_callback = help_callback
        self.parent_window = parent_window
        self.favorite_presets = FavoritePresetManager()

        self._build_ui()
        self.refresh_document_profiles()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        g = QGroupBox("Профили настроек")
        g_layout = QVBoxLayout(g)

        hbox_save = QHBoxLayout()
        btn_save = QPushButton("Сохранить профиль")
        btn_save.clicked.connect(self.save_current_profile)
        hbox_save.addWidget(btn_save)
        hbox_save.addWidget(self._create_help_button("profile_save"))
        g_layout.addLayout(hbox_save)

        hbox_load = QHBoxLayout()
        btn_load = QPushButton("Загрузить профиль")
        btn_load.clicked.connect(self.load_profile_file)
        hbox_load.addWidget(btn_load)
        hbox_load.addWidget(self._create_help_button("profile_load"))
        g_layout.addLayout(hbox_load)

        hbox_reset = QHBoxLayout()
        btn_reset = QPushButton("Сбросить к умолчанию")
        btn_reset.clicked.connect(self.reset_to_default)
        hbox_reset.addWidget(btn_reset)
        hbox_reset.addWidget(self._create_help_button("profile_reset"))
        g_layout.addLayout(hbox_reset)

        hbox_load_json = QHBoxLayout()
        btn_load_json = QPushButton("Загрузить JSON")
        btn_load_json.clicked.connect(self.load_json_settings)
        hbox_load_json.addWidget(btn_load_json)
        hbox_load_json.addWidget(self._create_help_button("json_load"))
        g_layout.addLayout(hbox_load_json)

        hbox_save_json = QHBoxLayout()
        btn_save_json = QPushButton("Сохранить JSON")
        btn_save_json.clicked.connect(self.save_json_settings)
        hbox_save_json.addWidget(btn_save_json)
        hbox_save_json.addWidget(self._create_help_button("json_save"))
        g_layout.addLayout(hbox_save_json)

        backup_button = QPushButton("Создать резервную копию настроек и проектов")
        backup_button.clicked.connect(self.create_backup)
        g_layout.addWidget(backup_button)
        merge_button = QPushButton("Объединить несколько DOCX…")
        merge_button.clicked.connect(self.merge_docx_files)
        g_layout.addWidget(merge_button)

        g_layout.addWidget(QLabel("Избранные настройки документа и презентации:"))
        favorite_row = QHBoxLayout()
        self.favorite_combo = QComboBox()
        favorite_row.addWidget(self.favorite_combo, 1)
        favorite_save = QPushButton("Сохранить текущие")
        favorite_save.clicked.connect(self.save_favorite_preset)
        favorite_apply = QPushButton("Применить")
        favorite_apply.clicked.connect(self.apply_favorite_preset)
        favorite_delete = QPushButton("Удалить")
        favorite_delete.clicked.connect(self.delete_favorite_preset)
        favorite_row.addWidget(favorite_save)
        favorite_row.addWidget(favorite_apply)
        favorite_row.addWidget(favorite_delete)
        g_layout.addLayout(favorite_row)
        self.refresh_favorite_presets()

        g_layout.addWidget(QLabel("Центр обновлений приложения"))
        update_row = QHBoxLayout()
        self.update_url_edit = QLineEdit(self.settings.get("update_manifest_url", ""))
        self.update_url_edit.setPlaceholderText("HTTPS-ссылка на JSON-манифест релизов")
        self.update_url_edit.textChanged.connect(lambda value: self.settings.set("update_manifest_url", value.strip()))
        update_row.addWidget(self.update_url_edit, 1)
        self.update_button = QPushButton("Проверить")
        self.update_button.clicked.connect(self.check_application_updates)
        update_row.addWidget(self.update_button)
        g_layout.addLayout(update_row)

        layout.addWidget(g)

        # Профили оформления именно DOCX (не путать с профилем настроек приложения).
        doc_group = QGroupBox("Оформление документов Word")
        doc_layout = QVBoxLayout(doc_group)
        doc_layout.addWidget(QLabel("Активный профиль оформления:"))
        self.document_profile_combo = QComboBox()
        self.document_profile_combo.currentIndexChanged.connect(self._on_document_profile_changed)
        doc_layout.addWidget(self.document_profile_combo)
        profile_buttons = QGridLayout()
        self.btn_profile_new = QPushButton("Создать")
        self.btn_profile_new.clicked.connect(self.create_document_profile)
        self.btn_profile_edit = QPushButton("Редактировать JSON")
        self.btn_profile_edit.clicked.connect(self.edit_document_profile)
        self.btn_profile_delete = QPushButton("Удалить")
        self.btn_profile_delete.clicked.connect(self.remove_document_profile)
        self.btn_profile_import = QPushButton("Импорт")
        self.btn_profile_import.clicked.connect(self.import_document_profile)
        self.btn_profile_export = QPushButton("Экспорт")
        self.btn_profile_export.clicked.connect(self.export_document_profile)
        for index, button in enumerate((self.btn_profile_new, self.btn_profile_edit, self.btn_profile_delete,
                                        self.btn_profile_import, self.btn_profile_export)):
            profile_buttons.addWidget(button, index // 3, index % 3)
        doc_layout.addLayout(profile_buttons)
        self.profile_description = QLabel("")
        self.profile_description.setWordWrap(True)
        doc_layout.addWidget(self.profile_description)
        layout.addWidget(doc_group)

        g = QGroupBox("Оформление интерфейса")
        g_layout = QVBoxLayout(g)
        self.palette_combo = QComboBox()
        self.palette_combo.currentIndexChanged.connect(self._on_palette_selected)
        g_layout.addWidget(QLabel("Цветовая тема:"))
        g_layout.addWidget(self.palette_combo)

        self.theme_color_buttons = {}
        color_grid = QGridLayout()
        color_labels = (("Фон окна", "background"), ("Панели", "surface"),
                        ("Поля ввода", "control"), ("Текст", "text"),
                        ("Акцент", "accent"), ("Границы", "border"))
        for index, (label, key) in enumerate(color_labels):
            color_grid.addWidget(QLabel(label), index, 0)
            button = QPushButton()
            button.clicked.connect(lambda _checked=False, color_key=key: self._choose_ui_color(color_key))
            self.theme_color_buttons[key] = button
            color_grid.addWidget(button, index, 1)
        g_layout.addLayout(color_grid)

        self.theme_preview = QWidget()
        preview_layout = QHBoxLayout(self.theme_preview)
        preview_layout.setContentsMargins(8, 6, 8, 6)
        self.theme_preview_label = QLabel("Предварительный просмотр интерфейса")
        self.theme_preview_button = QPushButton("Акцент")
        preview_layout.addWidget(self.theme_preview_label, 1)
        preview_layout.addWidget(self.theme_preview_button)
        g_layout.addWidget(self.theme_preview)

        self.palette_name_edit = QLineEdit()
        self.palette_name_edit.setPlaceholderText("Название пользовательской палитры")
        g_layout.addWidget(self.palette_name_edit)
        palette_actions = QHBoxLayout()
        save_palette = QPushButton("Сохранить палитру")
        save_palette.clicked.connect(self.save_custom_palette)
        palette_actions.addWidget(save_palette)
        save_appearance = QPushButton("Сохранить оформление")
        save_appearance.clicked.connect(self.save_appearance)
        palette_actions.addWidget(save_appearance)
        reset_appearance = QPushButton("Сбросить оформление")
        reset_appearance.clicked.connect(self.reset_appearance)
        palette_actions.addWidget(reset_appearance)
        g_layout.addLayout(palette_actions)
        self._refresh_palette_combo(self.settings.get("ui_palette_name", "Тёмная"))
        self._update_theme_controls()
        layout.addWidget(g)

        # ---- НОВЫЙ БЛОК: Режим отладки ----
        g_debug = QGroupBox("Отладка")
        g_debug_layout = QVBoxLayout(g_debug)
        self.debug_checkbox = QCheckBox("Включить режим отладки (подробное логирование)")
        self.debug_checkbox.setChecked(self.settings.get("debug_mode", False))
        self.debug_checkbox.stateChanged.connect(self._on_debug_toggled)
        g_debug_layout.addWidget(self.debug_checkbox)
        layout.addWidget(g_debug)

        layout.addStretch()

    def refresh_favorite_presets(self):
        if not hasattr(self, "favorite_combo"):
            return
        current = self.favorite_combo.currentText()
        self.favorite_combo.blockSignals(True)
        self.favorite_combo.clear()
        self.favorite_combo.addItems(self.favorite_presets.names())
        index = self.favorite_combo.findText(current)
        if index >= 0:
            self.favorite_combo.setCurrentIndex(index)
        self.favorite_combo.blockSignals(False)

    def merge_docx_files(self):
        if self.parent_window and hasattr(self.parent_window, "merge_docx_files_ui"):
            self.parent_window.merge_docx_files_ui()

    def check_application_updates(self):
        url = self.update_url_edit.text().strip()
        if not url:
            QMessageBox.information(
                self, "Центр обновлений",
                "Укажите HTTPS-ссылку на JSON-манифест вашего источника релизов.")
            return
        self.update_button.setEnabled(False)
        self.update_thread = UpdateCheckThread(url, self.settings.get("app_version", "8.0.0"), self)
        self.update_thread.finished_check.connect(self._show_update_result)
        self.update_thread.start()

    def _show_update_result(self, result, error):
        self.update_button.setEnabled(True)
        if error:
            QMessageBox.warning(self, "Центр обновлений", error)
            return
        if result["available"]:
            text = (f"Доступна версия {result['latest_version']} (сейчас {result['current_version']}).\n"
                    f"{result['notes']}\n{result['download_url']}")
        else:
            text = f"Установлена актуальная версия {result['current_version']}."
        QMessageBox.information(self, "Центр обновлений", text)

    def save_favorite_preset(self):
        name, accepted = QInputDialog.getText(self, "Избранные настройки", "Название набора:")
        if not accepted:
            return
        try:
            self.favorite_presets.save(name, self.settings.get_all())
            self.refresh_favorite_presets()
            self.favorite_combo.setCurrentText(name.strip())
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось сохранить", str(exc))

    def apply_favorite_preset(self):
        name = self.favorite_combo.currentText()
        data = self.favorite_presets.get(name) if name else None
        if data is None:
            QMessageBox.information(self, "Избранные настройки", "Сначала выберите сохранённый набор.")
            return
        self.settings.update(data)
        if self.parent_window and hasattr(self.parent_window, "sync_ui_from_settings"):
            self.parent_window.sync_ui_from_settings()
        QMessageBox.information(self, "Избранные настройки", f"Применён набор «{name}».")

    def delete_favorite_preset(self):
        name = self.favorite_combo.currentText()
        if not name:
            return
        if self.favorite_presets.delete(name):
            self.refresh_favorite_presets()

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

    def refresh_document_profiles(self, select_id=None):
        profiles = list_profiles()
        current = select_id or self.settings.get("document_profile", "jasmine")
        self.document_profile_combo.blockSignals(True)
        self.document_profile_combo.clear()
        for profile in profiles:
            self.document_profile_combo.addItem(profile.get("profile_name", profile["profile_id"]), profile["profile_id"])
        index = self.document_profile_combo.findData(current)
        if index < 0 and self.document_profile_combo.count():
            index = 0
        if index >= 0:
            self.document_profile_combo.setCurrentIndex(index)
        self.document_profile_combo.blockSignals(False)
        self._on_document_profile_changed(self.document_profile_combo.currentIndex())

    def _on_document_profile_changed(self, index):
        profile_id = self.document_profile_combo.itemData(index)
        if not profile_id:
            return
        self.settings.set("document_profile", profile_id)
        profile = get_profile(profile_id) or {}
        self.profile_description.setText(profile.get("description", ""))
        self.btn_profile_delete.setEnabled(profile_id not in ("jasmine", "legacy_gost"))

    def _profile_editor(self, title, initial_json):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(620, 620)
        layout = QVBoxLayout(dialog)
        editor = QPlainTextEdit(dialog)
        editor.setPlainText(json.dumps(initial_json, ensure_ascii=False, indent=2))
        layout.addWidget(editor)
        buttons = QHBoxLayout()
        save_btn, cancel_btn = QPushButton("Сохранить"), QPushButton("Отмена")
        save_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addWidget(save_btn); buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
        if dialog.exec() != QDialog.Accepted:
            return None
        try:
            data = json.loads(editor.toPlainText())
            if not isinstance(data, dict):
                raise ValueError("Корнем JSON должен быть объект")
            return data
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка профиля", f"Некорректный JSON: {exc}")
            return None

    def create_document_profile(self):
        name, ok = QInputDialog.getText(self, "Новый профиль", "Название профиля:")
        if not ok or not name.strip(): return
        profile_id, ok = QInputDialog.getText(self, "ID профиля", "Латинский ID (например, my_style):")
        if not ok or not profile_id.strip(): return
        base = get_profile(self.settings.get("document_profile", "jasmine")) or get_profile("jasmine") or {}
        data = dict(base)
        data["profile_id"] = profile_id.strip()
        data["profile_name"] = name.strip()
        data["description"] = "Пользовательский профиль оформления."
        try:
            save_profile(data, overwrite=False)
            self.refresh_document_profiles(data["profile_id"])
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось создать профиль", str(exc))

    def edit_document_profile(self):
        profile_id = self.document_profile_combo.currentData()
        profile = get_profile(profile_id) if profile_id else None
        if not profile: return
        edited = self._profile_editor(f"Редактирование: {profile.get('profile_name')}", profile)
        if edited is None: return
        # Встроенные профили разрешено редактировать, но нельзя менять их системный ID.
        edited["profile_id"] = profile_id
        try:
            save_profile(edited, overwrite=True)
            self.refresh_document_profiles(profile_id)
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка сохранения", str(exc))

    def remove_document_profile(self):
        profile_id = self.document_profile_combo.currentData()
        if not profile_id: return
        answer = QMessageBox.question(self, "Удаление профиля", "Удалить выбранный пользовательский профиль?")
        if answer != QMessageBox.Yes: return
        try:
            delete_profile(profile_id)
            self.settings.set("document_profile", "jasmine")
            self.refresh_document_profiles("jasmine")
        except Exception as exc:
            QMessageBox.warning(self, "Нельзя удалить профиль", str(exc))

    def import_document_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Импорт профиля", "", "JSON (*.json)")
        if not path: return
        try:
            with open(path, encoding="utf-8") as stream:
                data = json.load(stream)
            save_profile(data, overwrite=False)
            self.refresh_document_profiles(data.get("profile_id", data.get("id")))
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка импорта", str(exc))

    def export_document_profile(self):
        profile_id = self.document_profile_combo.currentData()
        profile = get_profile(profile_id) if profile_id else None
        if not profile: return
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт профиля", f"{profile_id}.json", "JSON (*.json)")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as stream:
                json.dump(profile, stream, ensure_ascii=False, indent=2)
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка экспорта", str(exc))

    def choose_accent_color(self):
        self._choose_ui_color("accent")

    def _current_ui_colors(self):
        legacy = self.settings.get("accent_color", "#7c4dff")
        return normalize_colors(self.settings.get("ui_colors"), legacy)

    def _refresh_palette_combo(self, selected_name=None):
        self.palette_combo.blockSignals(True)
        self.palette_combo.clear()
        for palette_id, palette in BUILTIN_PALETTES.items():
            self.palette_combo.addItem(palette["name"], {"kind": "builtin", "id": palette_id,
                                                          "colors": palette["colors"]})
        for palette in normalize_palettes(self.settings.get("ui_palettes", [])):
            self.palette_combo.addItem(palette["name"], {"kind": "custom", "colors": palette["colors"]})
        if selected_name and self.palette_combo.findText(selected_name) < 0:
            self.palette_combo.addItem(selected_name, {"kind": "current", "colors": self._current_ui_colors()})
        index = self.palette_combo.findText(selected_name or "")
        if index >= 0:
            self.palette_combo.setCurrentIndex(index)
        else:
            self.palette_combo.setCurrentIndex(0)
        self.palette_combo.blockSignals(False)

    def _on_palette_selected(self, index):
        if index < 0:
            return
        item = self.palette_combo.itemData(index) or {}
        try:
            colors = normalize_colors(item.get("colors"))
        except ValueError:
            colors = dict(DEFAULT_COLORS)
        self.settings.set("ui_colors", colors)
        self.settings.set("accent_color", colors["accent"])
        self.settings.set("ui_palette_name", self.palette_combo.itemText(index))
        self._update_theme_controls()
        if self.parent_window:
            self.parent_window.apply_style()

    def _choose_ui_color(self, key):
        colors = self._current_ui_colors()
        color = QColorDialog.getColor(QColor(colors[key]), self, f"Выберите цвет: {key}")
        if not color.isValid():
            return
        colors[key] = color.name()
        colors = normalize_colors(colors)
        self.settings.set("ui_colors", colors)
        self.settings.set("accent_color", colors["accent"])
        self.settings.set("ui_palette_name", "Пользовательская")
        self._refresh_palette_combo("Пользовательская")
        self._update_theme_controls()
        if self.parent_window:
            self.parent_window.apply_style()

    def _update_theme_controls(self):
        colors = self._current_ui_colors()
        for key, button in self.theme_color_buttons.items():
            button.setText(colors[key])
            button.setStyleSheet(f"background-color: {colors[key]}; color: {colors['text']};")
        self.theme_preview.setStyleSheet(
            f"background-color: {colors['surface']}; color: {colors['text']};"
            f"border: 1px solid {colors['border']}; border-radius: 5px;"
        )
        self.theme_preview_label.setStyleSheet(f"color: {colors['text']};")
        self.theme_preview_button.setStyleSheet(
            f"background-color: {colors['accent']}; color: {colors['text']}; padding: 5px 12px;"
        )

    def save_custom_palette(self):
        name = self.palette_name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "Название палитры", "Введите название пользовательской палитры.")
            return
        if any(name.casefold() == item["name"].casefold() for item in BUILTIN_PALETTES.values()):
            QMessageBox.information(self, "Название палитры", "Это название зарезервировано для встроенной темы.")
            return
        palettes = normalize_palettes(self.settings.get("ui_palettes", []))
        palette = {"name": name, "colors": self._current_ui_colors()}
        existing = next((i for i, item in enumerate(palettes)
                         if item["name"].casefold() == name.casefold()), None)
        if existing is None:
            palettes.append(palette)
        else:
            palettes[existing] = palette
        self.settings.set("ui_palettes", palettes)
        self.settings.set("ui_palette_name", name)
        self._refresh_palette_combo(name)
        self.save_appearance()

    def save_appearance(self):
        if self.parent_window:
            self.parent_window.save_appearance_settings()

    def reset_appearance(self):
        colors = dict(DEFAULT_COLORS)
        self.settings.set("ui_colors", colors)
        self.settings.set("accent_color", colors["accent"])
        self.settings.set("ui_palette_name", BUILTIN_PALETTES["dark"]["name"])
        self._refresh_palette_combo(BUILTIN_PALETTES["dark"]["name"])
        self._update_theme_controls()
        if self.parent_window:
            self.parent_window.apply_style()
            self.parent_window.save_appearance_settings()

    def _on_debug_toggled(self, state):
        enabled = state == Qt.Checked
        self.settings.set("debug_mode", enabled)
        if enabled:
            # При включении создаём логгер и пишем стартовое сообщение
            from logger import get_debug_logger
            get_debug_logger().debug("=== РЕЖИМ ОТЛАДКИ ВКЛЮЧЁН ===")

    # Остальные методы-прокси (без изменений)
    def save_current_profile(self):
        if self.parent_window:
            self.parent_window.save_current_profile()

    def load_profile_file(self):
        if self.parent_window:
            self.parent_window.load_profile_file()

    def reset_to_default(self):
        if self.parent_window:
            self.parent_window.reset_to_default()

    def load_json_settings(self):
        if self.parent_window:
            self.parent_window.load_json_settings()

    def save_json_settings(self):
        if self.parent_window:
            self.parent_window.save_json_settings()

    def create_backup(self):
        if self.parent_window:
            self.parent_window.create_backup()

    def update_accent_color(self):
        colors = self._current_ui_colors()
        accent = colors["accent"]
        self._update_theme_controls()
        for child in self.findChildren(QPushButton):
            if child.text() == "?":
                child.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {colors['control']};
                        color: {colors['text']};
                        border: 1px solid {colors['border']};
                        border-radius: 4px;
                        font-size: 10pt;
                    }}
                    QPushButton:hover {{
                        background-color: {accent};
                        color: white;
                    }}
                """)
