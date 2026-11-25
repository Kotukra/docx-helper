from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox


class HomeTab(QWidget):
    """Task-oriented start page that leaves advanced controls available."""
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        layout = QVBoxLayout(self)
        intro = QLabel("Создайте документ по ГОСТ, подготовьте презентацию или продолжите сохранённый проект.")
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 14px; padding: 8px;")
        layout.addWidget(intro)

        create_group = QGroupBox("Начать создание")
        create_layout = QHBoxLayout(create_group)
        word = QPushButton("Создать документ Word")
        word.setMinimumHeight(54)
        word.clicked.connect(lambda *_: self.parent_window.open_creation_wizard("docx"))
        presentation = QPushButton("Создать презентацию")
        presentation.setMinimumHeight(54)
        presentation.clicked.connect(lambda *_: self.parent_window.open_creation_wizard("pptx"))
        create_layout.addWidget(word)
        create_layout.addWidget(presentation)
        layout.addWidget(create_group)

        project_group = QGroupBox("Ваши материалы")
        project_layout = QHBoxLayout(project_group)
        continue_button = QPushButton("Продолжить последний проект")
        continue_button.clicked.connect(lambda *_: self.parent_window.open_latest_project())
        projects_button = QPushButton("Все проекты…")
        projects_button.clicked.connect(lambda *_: self.parent_window.open_project())
        recent_button = QPushButton("Недавние документы…")
        recent_button.clicked.connect(lambda *_: self.parent_window.show_recent_documents())
        project_layout.addWidget(continue_button)
        project_layout.addWidget(projects_button)
        project_layout.addWidget(recent_button)
        layout.addWidget(project_group)

        self.status = QLabel("Автосохранение последнего сеанса включено.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()

    def refresh(self, project_manager):
        projects = project_manager.list_projects()
        recent = project_manager.recent_documents()
        self.status.setText(
            f"Сохранённых проектов: {len(projects)}. Недавних созданных файлов: {len(recent)}. "
            "Автосохранение последнего сеанса включено."
        )
