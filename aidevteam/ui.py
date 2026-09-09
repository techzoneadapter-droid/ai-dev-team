from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .db import Database, app_data_dir
from .exporter import export_task_markdown
from .models import Outcome, ProjectRecord, Role, TaskRecord, TaskStatus
from .prompts import build_prompt, detect_outcome
from .services.browser_service import (
    detect_default_browser_candidates,
    discover_profiles,
    open_profile,
    validate_chat_url,
)
from .state_machine import allowed_outcomes, transition
from .version import __version__


APP_STYLE = """
QMainWindow, QWidget { background: #f7f8fa; color: #1f2937; font-family: 'Segoe UI'; font-size: 10pt; }
QGroupBox { background: white; border: 1px solid #dde2e8; border-radius: 8px; margin-top: 12px; padding: 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLineEdit, QTextEdit, QComboBox, QSpinBox, QListWidget, QTableWidget {
    background: white; border: 1px solid #cfd6df; border-radius: 6px; padding: 5px; selection-background-color: #2563eb;
}
QPushButton { background: #ffffff; border: 1px solid #c7ced8; border-radius: 6px; padding: 7px 12px; }
QPushButton:hover { background: #f0f4f8; }
QPushButton:disabled { color: #9ca3af; background: #f5f5f5; }
QPushButton#primary { background: #2563eb; color: white; border-color: #2563eb; font-weight: 600; }
QPushButton#primary:hover { background: #1d4ed8; }
QPushButton#danger { color: #b91c1c; }
QTabWidget::pane { border: 1px solid #d9dee6; background: #fff; }
QTabBar::tab { padding: 9px 16px; }
QHeaderView::section { background: #f2f4f7; padding: 6px; border: none; border-bottom: 1px solid #d9dee6; font-weight: 600; }
"""

STATUS_COLORS = {
    "Waiting": "#6b7280",
    "Active": "#1d4ed8",
    "Passed": "#15803d",
    "Failed": "#b91c1c",
    "Done": "#15803d",
}


class ProjectDialog(QDialog):
    def __init__(self, parent: QWidget, project: ProjectRecord | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Project" if project else "New Project")
        self.resize(620, 420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(project.name if project else "")
        self.description = QTextEdit(project.description if project else "")
        self.description.setFixedHeight(100)
        self.workspace = QLineEdit(project.workspace_path if project else "")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_workspace)
        workspace_row = QHBoxLayout()
        workspace_row.addWidget(self.workspace, 1)
        workspace_row.addWidget(browse)
        self.repo = QLineEdit(project.repo_url if project else "")
        self.repo.setPlaceholderText("Optional: https://github.com/owner/repo")
        form.addRow("Name *", self.name)
        form.addRow("Notes", self.description)
        form.addRow("Local workspace", workspace_row)
        form.addRow("Repository URL", self.repo)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_workspace(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select project workspace", self.workspace.text() or str(Path.home()))
        if path:
            self.workspace.setText(path)

    def _accept_if_valid(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Missing name", "Project name is required.")
            return
        self.accept()

    def values(self) -> tuple[str, str, str, str]:
        return (
            self.name.text().strip(),
            self.description.toPlainText().strip(),
            self.workspace.text().strip(),
            self.repo.text().strip(),
        )


class TaskEditDialog(QDialog):
    def __init__(self, parent: QWidget, task: TaskRecord) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Task")
        self.resize(700, 520)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title_edit = QLineEdit(task.title)
        self.body_edit = QTextEdit(task.task_text)
        form.addRow("Title", self.title_edit)
        form.addRow("Task", self.body_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_valid(self) -> None:
        if not self.body_edit.toPlainText().strip():
            QMessageBox.warning(self, "Missing task", "Task text cannot be empty.")
            return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"AI Dev Team v{__version__}")
        self.resize(1480, 940)
        self.setMinimumSize(1100, 720)
        self.db = Database()
        self.current_project_id: int | None = None
        self.current_task_id: int | None = None
        self.profile_widgets: dict[Role, dict[str, QWidget]] = {}
        self._build_ui()
        self._build_menu()
        self._build_shortcuts()
        self._load_projects()

    def closeEvent(self, event):  # type: ignore[override]
        self.db.close()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(14, 12, 14, 12)

        top = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("AI Dev Team")
        title.setFont(QFont("Segoe UI", 19, QFont.Weight.Bold))
        subtitle = QLabel("Developer → Reviewer → Tester, with local history and human-controlled browser profiles")
        subtitle.setStyleSheet("color: #667085;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        top.addLayout(title_col, 1)
        self.data_badge = QLabel("Local-only data")
        self.data_badge.setStyleSheet("background:#e8f5e9;color:#166534;padding:5px 9px;border-radius:8px;font-weight:600;")
        top.addWidget(self.data_badge)
        root_layout.addLayout(top)

        project_row = QHBoxLayout()
        project_row.addWidget(QLabel("Project:"))
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self._project_changed)
        project_row.addWidget(self.project_combo, 1)
        new_project_btn = QPushButton("New")
        new_project_btn.clicked.connect(self._new_project)
        project_row.addWidget(new_project_btn)
        edit_project_btn = QPushButton("Edit")
        edit_project_btn.clicked.connect(self._edit_project)
        project_row.addWidget(edit_project_btn)
        self.project_meta_label = QLabel("")
        self.project_meta_label.setStyleSheet("color:#667085;")
        project_row.addWidget(self.project_meta_label, 2)
        root_layout.addLayout(project_row)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_workflow_tab(), "Workflow")
        self.tabs.addTab(self._build_results_tab(), "Results & Activity")
        self.tabs.addTab(self._build_profiles_tab(), "Browser Profiles")
        self.tabs.addTab(self._build_settings_tab(), "Settings")
        root_layout.addWidget(self.tabs, 1)

        self.statusBar().showMessage(f"Database: {self.db.path}")

    def _build_workflow_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        head = QHBoxLayout()
        head.addWidget(QLabel("Tasks"))
        self.task_count_label = QLabel("0")
        self.task_count_label.setStyleSheet("color:#667085;")
        head.addWidget(self.task_count_label)
        head.addStretch(1)
        left_layout.addLayout(head)

        self.task_search = QLineEdit()
        self.task_search.setPlaceholderText("Filter tasks…")
        self.task_search.textChanged.connect(self._load_tasks)
        left_layout.addWidget(self.task_search)

        self.task_list = QListWidget()
        self.task_list.currentItemChanged.connect(self._task_changed)
        left_layout.addWidget(self.task_list, 1)

        task_actions = QHBoxLayout()
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_task)
        task_actions.addWidget(edit_btn)
        export_btn = QPushButton("Export .md")
        export_btn.clicked.connect(self._export_current_task)
        task_actions.addWidget(export_btn)
        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("danger")
        delete_btn.clicked.connect(self._delete_task)
        task_actions.addWidget(delete_btn)
        left_layout.addLayout(task_actions)

        create_box = QGroupBox("New task")
        create_layout = QVBoxLayout(create_box)
        self.task_title = QLineEdit()
        self.task_title.setPlaceholderText("Task title")
        create_layout.addWidget(self.task_title)
        self.task_input = QTextEdit()
        self.task_input.setPlaceholderText("Enter the overall task…")
        self.task_input.setFixedHeight(125)
        create_layout.addWidget(self.task_input)
        start_btn = QPushButton("Start Task")
        start_btn.setObjectName("primary")
        start_btn.clicked.connect(self._start_task)
        create_layout.addWidget(start_btn)
        left_layout.addWidget(create_box)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        status_box = QGroupBox("Current state")
        status_layout = QGridLayout(status_box)
        self.current_role_label = QLabel("-")
        self.iteration_label = QLabel("-")
        self.task_status_label = QLabel("-")
        status_layout.addWidget(QLabel("Role"), 0, 0)
        status_layout.addWidget(self.current_role_label, 0, 1)
        status_layout.addWidget(QLabel("Iteration"), 0, 2)
        status_layout.addWidget(self.iteration_label, 0, 3)
        status_layout.addWidget(QLabel("Status"), 0, 4)
        status_layout.addWidget(self.task_status_label, 0, 5)
        self.agent_status_labels: dict[Role, QLabel] = {}
        for idx, role in enumerate(Role):
            status_layout.addWidget(QLabel(role.value), 1, idx * 2)
            lab = QLabel("Waiting")
            self._style_agent_status(lab, "Waiting")
            status_layout.addWidget(lab, 1, idx * 2 + 1)
            self.agent_status_labels[role] = lab
        right_layout.addWidget(status_box)

        brief_box = QGroupBox("Original task")
        brief_layout = QVBoxLayout(brief_box)
        self.original_task_output = QTextEdit()
        self.original_task_output.setReadOnly(True)
        self.original_task_output.setMaximumHeight(115)
        brief_layout.addWidget(self.original_task_output)
        right_layout.addWidget(brief_box)

        action_row = QHBoxLayout()
        self.open_profile_btn = QPushButton("Open Profile")
        self.open_profile_btn.clicked.connect(self._open_current_profile)
        action_row.addWidget(self.open_profile_btn)
        self.copy_prompt_btn = QPushButton("Copy Prompt")
        self.copy_prompt_btn.clicked.connect(self._copy_prompt)
        action_row.addWidget(self.copy_prompt_btn)
        self.copy_open_btn = QPushButton("Copy + Open")
        self.copy_open_btn.setObjectName("primary")
        self.copy_open_btn.clicked.connect(self._copy_and_open)
        action_row.addWidget(self.copy_open_btn)
        refresh_btn = QPushButton("Refresh Prompt")
        refresh_btn.clicked.connect(self._refresh_task_view)
        action_row.addWidget(refresh_btn)
        action_row.addStretch(1)
        self.reopen_btn = QPushButton("Reopen Task")
        self.reopen_btn.clicked.connect(self._reopen_task)
        action_row.addWidget(self.reopen_btn)
        right_layout.addLayout(action_row)

        prompt_label = QLabel("Prompt for current role")
        prompt_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        right_layout.addWidget(prompt_label)
        self.prompt_output = QTextEdit()
        self.prompt_output.setReadOnly(True)
        self.prompt_output.setMinimumHeight(205)
        right_layout.addWidget(self.prompt_output, 2)

        result_group = QGroupBox("Record agent result")
        result_layout = QVBoxLayout(result_group)
        outcome_row = QHBoxLayout()
        outcome_row.addWidget(QLabel("Outcome:"))
        self.outcome_combo = QComboBox()
        outcome_row.addWidget(self.outcome_combo)
        self.detected_label = QLabel("")
        self.detected_label.setStyleSheet("color:#667085;")
        outcome_row.addWidget(self.detected_label)
        paste_btn = QPushButton("Paste Clipboard")
        paste_btn.clicked.connect(self._paste_clipboard)
        outcome_row.addWidget(paste_btn)
        outcome_row.addStretch(1)
        result_layout.addLayout(outcome_row)
        self.result_input = QTextEdit()
        self.result_input.setPlaceholderText("Paste the current agent response here. Reviewer/Tester PASS or FAIL is auto-detected from the first line.")
        self.result_input.setMinimumHeight(150)
        self.result_input.textChanged.connect(self._auto_detect_outcome)
        result_layout.addWidget(self.result_input)
        btn_row = QHBoxLayout()
        self.record_btn = QPushButton("Record Only")
        self.record_btn.clicked.connect(self._record_result)
        btn_row.addWidget(self.record_btn)
        self.next_btn = QPushButton("Record + Send to Next Role")
        self.next_btn.setObjectName("primary")
        self.next_btn.clicked.connect(self._send_next)
        btn_row.addWidget(self.next_btn)
        btn_row.addStretch(1)
        result_layout.addLayout(btn_row)
        right_layout.addWidget(result_group, 2)

        splitter.addWidget(right)
        splitter.setSizes([350, 1080])
        return page

    def _build_results_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        results_label = QLabel("Recorded results / handoffs for the selected task")
        results_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(results_label)
        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(["Time", "Iteration", "Role", "Outcome", "Preview"])
        self.results_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.itemSelectionChanged.connect(self._show_selected_result)
        layout.addWidget(self.results_table, 2)
        self.result_detail = QTextEdit()
        self.result_detail.setReadOnly(True)
        self.result_detail.setPlaceholderText("Select a recorded result to see full text.")
        layout.addWidget(self.result_detail, 1)

        activity_label = QLabel("Activity log")
        activity_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(activity_label)
        self.activity_table = QTableWidget(0, 5)
        self.activity_table.setHorizontalHeaderLabels(["Time", "Iteration", "Role", "Action", "Detail"])
        self.activity_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.activity_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.activity_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.activity_table, 2)
        return page

    def _build_profiles_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel(
            "Each role can launch a separate Chrome/Edge profile. AI Dev Team never reads or stores passwords, cookies, or session tokens. "
            "Profile discovery only reads Chromium's non-secret profile name metadata."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#475467;")
        layout.addWidget(note)

        candidates = detect_default_browser_candidates()
        default_browser = candidates[0] if candidates else ""
        for role in Role:
            box = QGroupBox(role.value)
            form = QFormLayout(box)
            exe = QLineEdit()
            exe_row = QHBoxLayout()
            exe_row.addWidget(exe, 1)
            browse_btn = QPushButton("Browse")
            browse_btn.clicked.connect(lambda _=False, r=role: self._browse_browser(r))
            exe_row.addWidget(browse_btn)
            detect_btn = QPushButton("Detect profiles")
            detect_btn.clicked.connect(lambda _=False, r=role: self._discover_profiles(r))
            exe_row.addWidget(detect_btn)
            form.addRow("Browser EXE", exe_row)

            profile = QComboBox()
            profile.setEditable(True)
            profile.setPlaceholderText("Default / Profile 1 / Profile 2…")
            form.addRow("Profile directory", profile)
            url = QLineEdit("https://chatgpt.com/")
            form.addRow("Chat URL", url)
            instruction = QTextEdit()
            instruction.setPlaceholderText(f"Optional persistent instruction for {role.value}…")
            instruction.setFixedHeight(72)
            form.addRow("Custom instruction", instruction)

            buttons = QHBoxLayout()
            save_btn = QPushButton(f"Save {role.value}")
            save_btn.setObjectName("primary")
            save_btn.clicked.connect(lambda _=False, r=role: self._save_profile(r))
            buttons.addWidget(save_btn)
            test_btn = QPushButton("Test Open")
            test_btn.clicked.connect(lambda _=False, r=role: self._test_profile(r))
            buttons.addWidget(test_btn)
            buttons.addStretch(1)
            form.addRow(buttons)
            self.profile_widgets[role] = {"exe": exe, "profile": profile, "url": url, "instruction": instruction}
            layout.addWidget(box)

            row = self.db.get_profile(role)
            exe.setText(row["browser_exe"] or default_browser)
            profile.setCurrentText(row["profile_dir"])
            url.setText(row["url"])
            instruction.setPlainText(row["custom_instruction"])
        layout.addStretch(1)
        return page

    def _build_settings_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        workflow_box = QGroupBox("Workflow preferences")
        form = QFormLayout(workflow_box)
        self.history_limit_spin = QSpinBox()
        self.history_limit_spin.setRange(1, 50)
        self.history_limit_spin.setValue(self.db.history_limit())
        form.addRow("Previous results included in prompts", self.history_limit_spin)
        self.auto_copy_check = QCheckBox("Copy the next prompt to clipboard after a transition")
        self.auto_copy_check.setChecked(self.db.bool_setting("auto_copy_on_transition"))
        form.addRow(self.auto_copy_check)
        self.auto_open_check = QCheckBox("Open the next role's browser profile after a transition")
        self.auto_open_check.setChecked(self.db.bool_setting("auto_open_on_transition"))
        form.addRow(self.auto_open_check)
        save_settings = QPushButton("Save Settings")
        save_settings.setObjectName("primary")
        save_settings.clicked.connect(self._save_settings)
        form.addRow(save_settings)
        layout.addWidget(workflow_box)

        data_box = QGroupBox("Local data")
        data_form = QFormLayout(data_box)
        db_path = QLineEdit(str(self.db.path))
        db_path.setReadOnly(True)
        data_form.addRow("SQLite database", db_path)
        data_actions = QHBoxLayout()
        open_data = QPushButton("Open Data Folder")
        open_data.clicked.connect(self._open_data_folder)
        data_actions.addWidget(open_data)
        backup = QPushButton("Backup Database…")
        backup.clicked.connect(self._backup_database)
        data_actions.addWidget(backup)
        export_project = QPushButton("Export Current Project JSON…")
        export_project.clicked.connect(self._export_project_json)
        data_actions.addWidget(export_project)
        data_actions.addStretch(1)
        data_form.addRow(data_actions)
        layout.addWidget(data_box)

        safety = QGroupBox("Browser safety boundary")
        safe_layout = QVBoxLayout(safety)
        safe_text = QLabel(
            "The app is intentionally limited to launching a configured browser executable/profile and helping you copy/paste prompts/results. "
            "It does not automate login, scrape ChatGPT DOM state, import cookies, or bypass service limits."
        )
        safe_text.setWordWrap(True)
        safe_layout.addWidget(safe_text)
        layout.addWidget(safety)
        layout.addStretch(1)
        return page

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        export_task = QAction("Export Current Task as Markdown…", self)
        export_task.triggered.connect(self._export_current_task)
        file_menu.addAction(export_task)
        export_project = QAction("Export Current Project as JSON…", self)
        export_project.triggered.connect(self._export_project_json)
        file_menu.addAction(export_project)
        backup = QAction("Backup Database…", self)
        backup.triggered.connect(self._backup_database)
        file_menu.addAction(backup)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        project_menu = self.menuBar().addMenu("Project")
        new_action = QAction("New Project", self)
        new_action.triggered.connect(self._new_project)
        project_menu.addAction(new_action)
        edit_action = QAction("Edit Current Project", self)
        edit_action.triggered.connect(self._edit_project)
        project_menu.addAction(edit_action)
        delete_action = QAction("Delete Current Project", self)
        delete_action.triggered.connect(self._delete_project)
        project_menu.addAction(delete_action)

        help_menu = self.menuBar().addMenu("Help")
        about = QAction("About", self)
        about.triggered.connect(self._about)
        help_menu.addAction(about)

    def _build_shortcuts(self) -> None:
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        self.copy_shortcut.activated.connect(self._copy_prompt)
        self.open_shortcut = QShortcut(QKeySequence("Ctrl+Shift+O"), self)
        self.open_shortcut.activated.connect(self._open_current_profile)
        self.next_shortcut = QShortcut(QKeySequence("Ctrl+Enter"), self)
        self.next_shortcut.activated.connect(self._send_next)

    def _load_projects(self, select_id: int | None = None) -> None:
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        projects = self.db.list_projects()
        if not projects:
            pid = self.db.create_project("Default Project")
            projects = self.db.list_projects()
            select_id = pid
        for project in projects:
            self.project_combo.addItem(project.name, project.id)
        self.project_combo.blockSignals(False)
        target = 0
        if select_id is not None:
            for idx in range(self.project_combo.count()):
                if self.project_combo.itemData(idx) == select_id:
                    target = idx
                    break
        self.project_combo.setCurrentIndex(target)
        self._project_changed(target)

    def _new_project(self) -> None:
        dialog = ProjectDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            pid = self.db.create_project(*dialog.values())
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Duplicate", "A project with that name already exists.")
            return
        self._load_projects(pid)

    def _edit_project(self) -> None:
        if self.current_project_id is None:
            return
        project = self.db.get_project(self.current_project_id)
        dialog = ProjectDialog(self, project)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.db.update_project(project.id, *dialog.values())
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Duplicate", "A project with that name already exists.")
            return
        self._load_projects(project.id)

    def _delete_project(self) -> None:
        if self.current_project_id is None:
            return
        project = self.db.get_project(self.current_project_id)
        answer = QMessageBox.question(
            self,
            "Delete project",
            f"Delete '{project.name}' and all of its tasks/history? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_project(project.id)
        self.current_project_id = None
        self.current_task_id = None
        self._load_projects()

    def _project_changed(self, index: int) -> None:
        if index < 0 or self.project_combo.itemData(index) is None:
            return
        self.current_project_id = int(self.project_combo.itemData(index))
        project = self.db.get_project(self.current_project_id)
        meta: list[str] = []
        if project.workspace_path:
            meta.append(Path(project.workspace_path).name or project.workspace_path)
        if project.repo_url:
            meta.append(project.repo_url.removeprefix("https://github.com/"))
        self.project_meta_label.setText(" • ".join(meta))
        self._load_tasks()

    def _load_tasks(self, *_args, select_id: int | None = None) -> None:
        previous = select_id or self.current_task_id
        self.task_list.blockSignals(True)
        self.task_list.clear()
        tasks: list[TaskRecord] = []
        if self.current_project_id is not None:
            tasks = self.db.list_tasks(self.current_project_id)
            query = self.task_search.text().strip().lower() if hasattr(self, "task_search") else ""
            if query:
                tasks = [t for t in tasks if query in t.title.lower() or query in t.task_text.lower()]
            for task in tasks:
                marker = "✓" if task.status == TaskStatus.DONE else "→"
                item = QListWidgetItem(f"{marker}  #{task.id}  {task.title}\n    {task.status.value} · Iteration {task.iteration} · {task.current_role.value}")
                item.setData(Qt.ItemDataRole.UserRole, task.id)
                self.task_list.addItem(item)
        self.task_count_label.setText(str(len(tasks)))
        self.task_list.blockSignals(False)
        selected = False
        if previous is not None:
            for idx in range(self.task_list.count()):
                if self.task_list.item(idx).data(Qt.ItemDataRole.UserRole) == previous:
                    self.task_list.setCurrentRow(idx)
                    self._task_changed(self.task_list.item(idx), None)
                    selected = True
                    break
        if not selected and self.task_list.count() > 0:
            self.task_list.setCurrentRow(0)
            self._task_changed(self.task_list.currentItem(), None)
        elif self.task_list.count() == 0:
            self.current_task_id = None
            self._clear_task_view()

    def _start_task(self) -> None:
        if self.current_project_id is None:
            return
        title = self.task_title.text().strip() or "Untitled Task"
        text = self.task_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Missing task", "Enter the overall task first.")
            return
        task_id = self.db.create_task(self.current_project_id, title, text)
        self.task_title.clear()
        self.task_input.clear()
        self.current_task_id = task_id
        self._load_tasks(select_id=task_id)

    def _task_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        self.current_task_id = int(current.data(Qt.ItemDataRole.UserRole))
        self._refresh_task_view()

    def _edit_task(self) -> None:
        if self.current_task_id is None:
            return
        task = self.db.get_task(self.current_task_id)
        dialog = TaskEditDialog(self, task)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.db.update_task_content(task.id, dialog.title_edit.text().strip() or "Untitled Task", dialog.body_edit.toPlainText().strip())
        self.db.add_activity(task.id, task.current_role, task.iteration, "Task edited", "Title/task text updated")
        self._load_tasks(select_id=task.id)

    def _delete_task(self) -> None:
        if self.current_task_id is None:
            return
        task = self.db.get_task(self.current_task_id)
        answer = QMessageBox.question(
            self,
            "Delete task",
            f"Delete task '{task.title}' and all recorded history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_task(task.id)
        self.current_task_id = None
        self._load_tasks()

    def _reopen_task(self) -> None:
        if self.current_task_id is None:
            return
        task = self.db.get_task(self.current_task_id)
        if task.status != TaskStatus.DONE:
            return
        answer = QMessageBox.question(
            self,
            "Reopen task",
            "Reopen this completed task as a new Developer iteration?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.db.reopen_task(task.id)
            self._load_tasks(select_id=task.id)

    def _clear_task_view(self) -> None:
        self.current_role_label.setText("-")
        self.iteration_label.setText("-")
        self.task_status_label.setText("-")
        self.original_task_output.clear()
        self.prompt_output.clear()
        self.result_input.clear()
        self.results_table.setRowCount(0)
        self.activity_table.setRowCount(0)
        self.result_detail.clear()
        self.reopen_btn.setVisible(False)
        for lab in self.agent_status_labels.values():
            self._style_agent_status(lab, "Waiting")
        for w in [self.open_profile_btn, self.copy_prompt_btn, self.copy_open_btn, self.record_btn, self.next_btn]:
            w.setEnabled(False)

    def _refresh_task_view(self) -> None:
        if self.current_task_id is None:
            self._clear_task_view()
            return
        try:
            task = self.db.get_task(self.current_task_id)
        except KeyError:
            self.current_task_id = None
            self._clear_task_view()
            return
        self.current_role_label.setText(task.current_role.value)
        self.iteration_label.setText(str(task.iteration))
        self.task_status_label.setText(task.status.value)
        self.original_task_output.setPlainText(task.task_text)
        self.prompt_output.setPlainText(build_prompt(self.db, task) if task.status != TaskStatus.DONE else "Task completed. Use Reopen Task to start a new Developer iteration.")
        self._update_outcome_choices(task)
        self._update_agent_statuses(task)
        self._load_results_and_activity()
        done = task.status == TaskStatus.DONE
        self.reopen_btn.setVisible(done)
        for w in [self.open_profile_btn, self.copy_prompt_btn, self.copy_open_btn, self.record_btn, self.next_btn]:
            w.setEnabled(not done)
        self._auto_detect_outcome()

    def _update_outcome_choices(self, task: TaskRecord) -> None:
        self.outcome_combo.blockSignals(True)
        self.outcome_combo.clear()
        for outcome in allowed_outcomes(task.current_role, task.status):
            self.outcome_combo.addItem(outcome.value)
        self.outcome_combo.blockSignals(False)

    def _update_agent_statuses(self, task: TaskRecord) -> None:
        for lab in self.agent_status_labels.values():
            self._style_agent_status(lab, "Waiting")
        if task.status == TaskStatus.DONE:
            self._style_agent_status(self.agent_status_labels[Role.DEVELOPER], "Passed")
            self._style_agent_status(self.agent_status_labels[Role.REVIEWER], "Passed")
            self._style_agent_status(self.agent_status_labels[Role.TESTER], "Done")
            return
        for role in Role:
            latest = self.db.latest_result(task.id, role)
            if latest:
                status = "Failed" if latest.outcome == Outcome.FAIL else "Passed"
                self._style_agent_status(self.agent_status_labels[role], status)
        self._style_agent_status(self.agent_status_labels[task.current_role], "Active")

    def _style_agent_status(self, label: QLabel, status: str) -> None:
        color = STATUS_COLORS.get(status, "#6b7280")
        label.setText(status)
        label.setStyleSheet(f"font-weight:700;color:{color};")

    def _load_results_and_activity(self) -> None:
        if self.current_task_id is None:
            return
        results = self.db.list_results(self.current_task_id)
        self.results_table.setRowCount(len(results))
        for row_idx, result in enumerate(results):
            preview = " ".join(result.result_text.split())[:180]
            vals = [result.created_at, str(result.iteration), result.role.value, result.outcome.value, preview]
            for col_idx, value in enumerate(vals):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, result.id)
                self.results_table.setItem(row_idx, col_idx, item)
        activity = self.db.list_activity(self.current_task_id)
        self.activity_table.setRowCount(len(activity))
        for row_idx, rec in enumerate(activity):
            vals = [rec.created_at, str(rec.iteration), rec.role.value if rec.role else "-", rec.action, rec.detail]
            for col_idx, value in enumerate(vals):
                self.activity_table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def _show_selected_result(self) -> None:
        if self.current_task_id is None:
            return
        row = self.results_table.currentRow()
        if row < 0:
            return
        result_id = self.results_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        for result in self.db.list_results(self.current_task_id):
            if result.id == result_id:
                self.result_detail.setPlainText(result.result_text)
                break

    def _auto_detect_outcome(self) -> None:
        if self.current_task_id is None:
            return
        task = self.db.get_task(self.current_task_id)
        detected = detect_outcome(self.result_input.toPlainText(), task.current_role)
        if detected and self.outcome_combo.findText(detected.value) >= 0:
            self.outcome_combo.setCurrentText(detected.value)
            if task.current_role != Role.DEVELOPER:
                self.detected_label.setText(f"Detected: {detected.value}")
            else:
                self.detected_label.setText("")
        elif task.current_role != Role.DEVELOPER and self.result_input.toPlainText().strip():
            self.detected_label.setText("No PASS/FAIL detected on first line")
        else:
            self.detected_label.setText("")

    def _record_result(self) -> bool:
        if self.current_task_id is None:
            return False
        task = self.db.get_task(self.current_task_id)
        if task.status == TaskStatus.DONE:
            return False
        text = self.result_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Missing result", "Paste or enter the agent result first.")
            return False
        if self.outcome_combo.count() == 0:
            return False
        outcome = Outcome(self.outcome_combo.currentText())
        if outcome not in allowed_outcomes(task.current_role, task.status):
            QMessageBox.warning(self, "Invalid outcome", f"Invalid outcome for {task.current_role.value}.")
            return False
        self.db.add_result(task.id, task.current_role, task.iteration, outcome, text)
        self.db.add_activity(task.id, task.current_role, task.iteration, "Result recorded", outcome.value)
        self._load_results_and_activity()
        return True

    def _send_next(self) -> None:
        if self.current_task_id is None:
            return
        task = self.db.get_task(self.current_task_id)
        if task.status == TaskStatus.DONE:
            return
        text = self.result_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Missing result", "Paste the current agent result before moving the workflow.")
            return
        if self.outcome_combo.count() == 0:
            return
        outcome = Outcome(self.outcome_combo.currentText())
        try:
            tr = transition(task.current_role, task.iteration, outcome)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid outcome", str(exc))
            return

        latest = self.db.latest_result(task.id)
        duplicate = (
            latest is not None
            and latest.role == task.current_role
            and latest.iteration == task.iteration
            and latest.outcome == outcome
            and latest.result_text == text
        )
        if not duplicate:
            self.db.add_result(task.id, task.current_role, task.iteration, outcome, text)
            self.db.add_activity(task.id, task.current_role, task.iteration, "Result recorded", outcome.value)

        self.db.update_task_state(task.id, tr.next_role, tr.next_iteration, tr.task_status)
        self.db.add_activity(task.id, tr.next_role, tr.next_iteration, "State transition", tr.detail)
        self.result_input.clear()
        self._load_tasks(select_id=task.id)

        if tr.task_status == TaskStatus.DONE:
            QMessageBox.information(self, "Done", "Tester passed the task. Workflow is complete.")
            return
        if self.db.bool_setting("auto_copy_on_transition"):
            self._copy_prompt()
        if self.db.bool_setting("auto_open_on_transition"):
            self._open_current_profile()

    def _browse_browser(self, role: Role) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select browser executable", "", "Executable (*.exe);;All files (*)")
        if path:
            exe = self.profile_widgets[role]["exe"]
            assert isinstance(exe, QLineEdit)
            exe.setText(path)
            self._discover_profiles(role)

    def _discover_profiles(self, role: Role) -> None:
        widgets = self.profile_widgets[role]
        exe = widgets["exe"]
        profile = widgets["profile"]
        assert isinstance(exe, QLineEdit) and isinstance(profile, QComboBox)
        profiles = discover_profiles(exe.text())
        current = profile.currentText()
        profile.clear()
        for directory, display_name in profiles:
            profile.addItem(f"{display_name}  [{directory}]", directory)
        profile.setEditable(True)
        if current:
            match = profile.findData(current)
            if match >= 0:
                profile.setCurrentIndex(match)
            else:
                profile.setCurrentText(current)
        if not profiles:
            QMessageBox.information(self, "No profiles detected", "No Chrome/Edge profiles were found automatically. You can enter Default or Profile 1 manually.")

    def _profile_dir_value(self, combo: QComboBox) -> str:
        data = combo.currentData()
        if data and combo.currentText().endswith(f"[{data}]"):
            return str(data)
        return combo.currentText().strip()

    def _save_profile(self, role: Role) -> None:
        widgets = self.profile_widgets[role]
        exe, profile, url, instruction = widgets["exe"], widgets["profile"], widgets["url"], widgets["instruction"]
        assert isinstance(exe, QLineEdit) and isinstance(profile, QComboBox) and isinstance(url, QLineEdit) and isinstance(instruction, QTextEdit)
        try:
            clean_url = validate_chat_url(url.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid URL", str(exc))
            return
        self.db.save_profile(role, exe.text(), self._profile_dir_value(profile), clean_url, instruction.toPlainText())
        QMessageBox.information(self, "Saved", f"{role.value} profile and instructions saved locally.")
        if self.current_task_id is not None:
            self._refresh_task_view()

    def _test_profile(self, role: Role) -> None:
        widgets = self.profile_widgets[role]
        exe, profile, url = widgets["exe"], widgets["profile"], widgets["url"]
        assert isinstance(exe, QLineEdit) and isinstance(profile, QComboBox) and isinstance(url, QLineEdit)
        try:
            open_profile(exe.text(), self._profile_dir_value(profile), url.text())
        except Exception as exc:
            QMessageBox.critical(self, "Cannot open profile", str(exc))

    def _open_current_profile(self) -> None:
        if self.current_task_id is None:
            return
        task = self.db.get_task(self.current_task_id)
        row = self.db.get_profile(task.current_role)
        try:
            open_profile(row["browser_exe"], row["profile_dir"], row["url"])
            self.db.add_activity(task.id, task.current_role, task.iteration, "Profile opened", row["profile_dir"] or "Default")
            self._load_results_and_activity()
        except Exception as exc:
            QMessageBox.critical(self, "Cannot open profile", str(exc))

    def _copy_prompt(self) -> None:
        text = self.prompt_output.toPlainText().strip()
        if not text or self.current_task_id is None:
            return
        QApplication.clipboard().setText(text)
        task = self.db.get_task(self.current_task_id)
        self.db.add_activity(task.id, task.current_role, task.iteration, "Prompt copied", "Copied to clipboard")
        self._load_results_and_activity()
        self.statusBar().showMessage(f"{task.current_role.value} prompt copied", 3000)

    def _copy_and_open(self) -> None:
        self._copy_prompt()
        self._open_current_profile()

    def _paste_clipboard(self) -> None:
        self.result_input.setPlainText(QApplication.clipboard().text())
        self._auto_detect_outcome()

    def _export_current_task(self) -> None:
        if self.current_task_id is None:
            QMessageBox.information(self, "No task", "Select a task first.")
            return
        task = self.db.get_task(self.current_task_id)
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in task.title).strip() or f"task-{task.id}"
        path, _ = QFileDialog.getSaveFileName(self, "Export task", f"{safe}.md", "Markdown (*.md)")
        if not path:
            return
        export_task_markdown(self.db, task.id, Path(path))
        self.statusBar().showMessage(f"Exported: {path}", 5000)

    def _export_project_json(self) -> None:
        if self.current_project_id is None:
            return
        project = self.db.get_project(self.current_project_id)
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in project.name).strip() or "project"
        path, _ = QFileDialog.getSaveFileName(self, "Export project", f"{safe}.json", "JSON (*.json)")
        if not path:
            return
        self.db.export_project_json(project.id, Path(path))
        self.statusBar().showMessage(f"Exported: {path}", 5000)

    def _backup_database(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path, _ = QFileDialog.getSaveFileName(self, "Backup database", f"aidevteam-backup-{stamp}.db", "SQLite database (*.db)")
        if not path:
            return
        self.db.backup_to(Path(path))
        QMessageBox.information(self, "Backup complete", f"Database backup saved to:\n{path}")

    def _open_data_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_data_dir())))

    def _save_settings(self) -> None:
        self.db.set_setting("history_limit", str(self.history_limit_spin.value()))
        self.db.set_setting("auto_copy_on_transition", "true" if self.auto_copy_check.isChecked() else "false")
        self.db.set_setting("auto_open_on_transition", "true" if self.auto_open_check.isChecked() else "false")
        if self.current_task_id is not None:
            self._refresh_task_view()
        QMessageBox.information(self, "Saved", "Workflow settings saved locally.")

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "About AI Dev Team",
            f"AI Dev Team v{__version__}\n\nLocal Windows orchestration for Developer → Reviewer → Tester browser workflows.\n\nNo ChatGPT credentials, cookies, or session tokens are stored.",
        )


def run() -> None:
    app = QApplication([])
    app.setApplicationName("AI Dev Team")
    app.setOrganizationName("AI Dev Team")
    app.setStyleSheet(APP_STYLE)
    win = MainWindow()
    win.show()
    app.exec()
