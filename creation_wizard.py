"""A compact guided flow for choosing output, material, and document style."""
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QWizard, QWizardPage, QTextEdit, QVBoxLayout,
)

from document_profile_manager import list_profiles
from processor import read_file_content
from quality_checks import inspect_text


class _TextPage(QWizardPage):
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("Добавьте материал")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Вставьте текст или загрузите TXT, DOCX, PDF, HTML, Markdown либо ODT."))
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)
        self.detected_label = QLabel("Определение структуры появится после ввода материала.")
        self.editor.textChanged.connect(self._text_changed)
        layout.addWidget(self.editor)
        layout.addWidget(self.detected_label)
        load = QPushButton("Загрузить файл")
        load.clicked.connect(self.load_file)
        layout.addWidget(load)

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите материал", "",
            "Поддерживаемые файлы (*.txt *.docx *.pdf *.html *.htm *.md *.odt)",
        )
        if not path:
            return
        try:
            self.editor.setPlainText(read_file_content(path))
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось прочитать файл", str(exc))

    def isComplete(self):
        return bool(self.editor.toPlainText().strip())

    def _text_changed(self):
        report = inspect_text(self.editor.toPlainText(), self.wizard.settings.get_all())
        self.detected_label.setText(f"Автоопределение: {report['content_type']}")
        self.completeChanged.emit()


class _StylePage(QWizardPage):
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("Выберите оформление")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Профиль оформления Word"))
        self.profile_combo = QComboBox()
        self.profiles = list_profiles()
        for profile in self.profiles:
            self.profile_combo.addItem(profile.get("profile_name", profile["profile_id"]),
                                       profile["profile_id"])
        current_profile = wizard.settings.get("document_profile", "jasmine")
        selected_profile = self.profile_combo.findData(current_profile)
        if selected_profile >= 0:
            self.profile_combo.setCurrentIndex(selected_profile)
        layout.addWidget(self.profile_combo)

        layout.addWidget(QLabel("Шаблон презентации PowerPoint"))
        template_row = QHBoxLayout()
        self.template_combo = QComboBox()
        self._scan_templates()
        self.template_combo.currentIndexChanged.connect(lambda *_: self.completeChanged.emit())
        template_row.addWidget(self.template_combo, 1)
        browse = QPushButton("Выбрать файл…")
        browse.clicked.connect(self.choose_template)
        template_row.addWidget(browse)
        layout.addLayout(template_row)
        layout.addWidget(QLabel("Выбор Word профиля и шаблона презентации сохраняется отдельно."))

    def _scan_templates(self):
        folder = Path(self.wizard.settings.get("ppt_template_folder", "templates_ppt"))
        if not folder.is_absolute():
            folder = Path(__file__).resolve().parent / folder
        current = self.wizard.settings.get("ppt_template_path", "")
        paths = sorted(folder.glob("*.pptx")) if folder.is_dir() else []
        if current and Path(current).is_file() and Path(current) not in paths:
            paths.insert(0, Path(current))
        for path in paths:
            self.template_combo.addItem(path.name, str(path))
        if not paths:
            self.template_combo.addItem("Шаблоны не найдены — выберите файл", "")
        if current:
            index = self.template_combo.findData(current)
            if index >= 0:
                self.template_combo.setCurrentIndex(index)

    def choose_template(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите шаблон презентации", "", "PowerPoint (*.pptx)")
        if path:
            index = self.template_combo.findData(path)
            if index < 0:
                self.template_combo.addItem(Path(path).name, path)
                index = self.template_combo.count() - 1
            self.template_combo.setCurrentIndex(index)

    def isComplete(self):
        return self.wizard.mode_combo.currentData() != "pptx" or bool(self.template_combo.currentData())


class _ReviewPage(QWizardPage):
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("Проверьте параметры")
        layout = QVBoxLayout(self)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

    def initializePage(self):
        self.summary.setText(self.wizard.summary_text())


class CreationWizard(QWizard):
    def __init__(self, settings, parent=None, default_mode=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Помощник создания документа")
        self.setWizardStyle(QWizard.ModernStyle)

        mode_page = QWizardPage()
        mode_page.setTitle("Что создаём?")
        mode_layout = QVBoxLayout(mode_page)
        mode_layout.addWidget(QLabel("Выберите тип результата."))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Документ Word по ГОСТ", "docx")
        self.mode_combo.addItem("Презентацию PowerPoint", "pptx")
        initial_mode = default_mode if default_mode in ("docx", "pptx") else (
            "pptx" if settings.get("app_mode", 0) == 1 else "docx")
        self.mode_combo.setCurrentIndex(1 if initial_mode == "pptx" else 0)
        mode_layout.addWidget(self.mode_combo)

        self.text_page = _TextPage(self)
        self.style_page = _StylePage(self)
        self.review_page = _ReviewPage(self)
        self.mode_combo.currentIndexChanged.connect(lambda *_: self.style_page.completeChanged.emit())
        self.addPage(mode_page)
        self.addPage(self.text_page)
        self.addPage(self.style_page)
        self.addPage(self.review_page)

    def summary_text(self):
        mode = self.mode_combo.currentData()
        text = self.text_page.editor.toPlainText().strip()
        if mode == "pptx":
            template = self.style_page.template_combo.currentText()
            return (f"Результат: презентация PowerPoint\nШаблон: {template}\n"
                    f"Материал: {len(text)} символов\n\nПосле нажатия «Готово» начнётся создание презентации.")
        profile = self.style_page.profile_combo.currentText()
        return (f"Результат: документ Word по ГОСТ\nПрофиль: {profile}\n"
                f"Материал: {len(text)} символов\n\nПосле нажатия «Готово» начнётся создание документа.")

    def result_data(self):
        return {
            "mode": self.mode_combo.currentData(),
            "text": self.text_page.editor.toPlainText(),
            "document_profile": self.style_page.profile_combo.currentData(),
            "ppt_template_path": self.style_page.template_combo.currentData(),
        }
