from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from .db import Database
from .models import Outcome, Role, TaskStatus
from .prompts import build_prompt
from .services.browser_service import detect_default_browser_candidates, open_profile
from .state_machine import transition


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AI Dev Team")
        self.resize(1380, 900)
        self.db = Database()
        self.current_project_id: int | None = None
        self.current_task_id: int | None = None
        self.profile_widgets: dict[Role, dict[str, QWidget]] = {}
        self._build_ui()
        self._load_projects()

    def closeEvent(self, event):  # type: ignore[override]
        self.db.close()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)

        title = QLabel("AI Dev Team")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        subtitle = QLabel("Human-in-the-loop orchestration for 3 separate ChatGPT browser profiles")
        subtitle.setStyleSheet("color: #666;")
        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)

        project_row = QHBoxLayout()
        project_row.addWidget(QLabel("Project:"))
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self._project_changed)
        project_row.addWidget(self.project_combo, 1)
        new_project_btn = QPushButton("New Project")
        new_project_btn.clicked.connect(self._new_project)
        project_row.addWidget(new_project_btn)
        root_layout.addLayout(project_row)

        tabs = QTabWidget()
        tabs.addTab(self._build_workflow_tab(), "Workflow")
        tabs.addTab(self._build_profiles_tab(), "Browser Profiles")
        root_layout.addWidget(tabs, 1)

    def _build_workflow_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Tasks"))
        self.task_list = QListWidget()
        self.task_list.currentItemChanged.connect(self._task_changed)
        left_layout.addWidget(self.task_list, 1)

        self.task_title = QLineEdit()
        self.task_title.setPlaceholderText("Task title")
        left_layout.addWidget(self.task_title)
        self.task_input = QTextEdit()
        self.task_input.setPlaceholderText("Enter the overall task here...")
        self.task_input.setFixedHeight(140)
        left_layout.addWidget(self.task_input)
        start_btn = QPushButton("Start Task")
        start_btn.clicked.connect(self._start_task)
        left_layout.addWidget(start_btn)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        status_box = QGroupBox("Current state")
        status_layout = QGridLayout(status_box)
        self.current_role_label = QLabel("-")
        self.iteration_label = QLabel("-")
        self.task_status_label = QLabel("-")
        self.agent_status_labels: dict[Role, QLabel] = {}
        status_layout.addWidget(QLabel("Current role"), 0, 0)
        status_layout.addWidget(self.current_role_label, 0, 1)
        status_layout.addWidget(QLabel("Iteration"), 0, 2)
        status_layout.addWidget(self.iteration_label, 0, 3)
        status_layout.addWidget(QLabel("Task status"), 0, 4)
        status_layout.addWidget(self.task_status_label, 0, 5)
        for idx, role in enumerate(Role):
            status_layout.addWidget(QLabel(role.value), 1, idx * 2)
            lab = QLabel("Waiting")
            lab.setStyleSheet("font-weight: 600;")
            status_layout.addWidget(lab, 1, idx * 2 + 1)
            self.agent_status_labels[role] = lab
        right_layout.addWidget(status_box)

        action_row = QHBoxLayout()
        self.open_profile_btn = QPushButton("Open Profile")
        self.open_profile_btn.clicked.connect(self._open_current_profile)
        action_row.addWidget(self.open_profile_btn)
        self.copy_prompt_btn = QPushButton("Copy Prompt")
        self.copy_prompt_btn.clicked.connect(self._copy_prompt)
        action_row.addWidget(self.copy_prompt_btn)
        self.refresh_prompt_btn = QPushButton("Refresh Prompt")
        self.refresh_prompt_btn.clicked.connect(self._refresh_task_view)
        action_row.addWidget(self.refresh_prompt_btn)
        action_row.addStretch(1)
        right_layout.addLayout(action_row)

        prompt_label = QLabel("Prompt for current role")
        prompt_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        right_layout.addWidget(prompt_label)
        self.prompt_output = QTextEdit()
        self.prompt_output.setReadOnly(True)
        self.prompt_output.setMinimumHeight(220)
        right_layout.addWidget(self.prompt_output)

        result_group = QGroupBox("Paste / Record result")
        result_layout = QVBoxLayout(result_group)
        outcome_row = QHBoxLayout()
        outcome_row.addWidget(QLabel("Outcome:"))
        self.outcome_combo = QComboBox()
        self.outcome_combo.addItems([Outcome.SUBMITTED.value, Outcome.PASS.value, Outcome.FAIL.value])
        outcome_row.addWidget(self.outcome_combo)
        paste_btn = QPushButton("Paste Clipboard")
        paste_btn.clicked.connect(self._paste_clipboard)
        outcome_row.addWidget(paste_btn)
        outcome_row.addStretch(1)
        result_layout.addLayout(outcome_row)
        self.result_input = QTextEdit()
        self.result_input.setPlaceholderText("Paste the agent response here...")
        self.result_input.setMinimumHeight(170)
        result_layout.addWidget(self.result_input)
        btn_row = QHBoxLayout()
        self.record_btn = QPushButton("Record Result")
        self.record_btn.clicked.connect(self._record_result)
        btn_row.addWidget(self.record_btn)
        self.next_btn = QPushButton("Send to Next Role")
        self.next_btn.clicked.connect(self._send_next)
        btn_row.addWidget(self.next_btn)
        btn_row.addStretch(1)
        result_layout.addLayout(btn_row)
        right_layout.addWidget(result_group)

        activity_label = QLabel("Activity log")
        activity_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        right_layout.addWidget(activity_label)
        self.activity_table = QTableWidget(0, 5)
        self.activity_table.setHorizontalHeaderLabels(["Time", "Iteration", "Role", "Action", "Detail"])
        self.activity_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.activity_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.activity_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        right_layout.addWidget(self.activity_table, 1)

        splitter.addWidget(right)
        splitter.setSizes([320, 1000])
        return page

    def _build_profiles_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel(
            "Configure one browser executable + profile directory per role. "
            "The app only launches the browser profile and URL; it does not read or store login credentials, cookies, or session tokens."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        candidates = detect_default_browser_candidates()
        default_browser = candidates[0] if candidates else ""

        for role in Role:
            box = QGroupBox(role.value)
            form = QFormLayout(box)
            exe_row = QHBoxLayout()
            exe = QLineEdit()
            exe_row.addWidget(exe, 1)
            browse_btn = QPushButton("Browse")
            browse_btn.clicked.connect(lambda _=False, r=role: self._browse_browser(r))
            exe_row.addWidget(browse_btn)
            form.addRow("Browser EXE", exe_row)
            profile = QLineEdit()
            profile.setPlaceholderText("Example: Default or Profile 1")
            form.addRow("Profile directory", profile)
            url = QLineEdit("https://chatgpt.com/")
            form.addRow("Chat URL", url)
            save_btn = QPushButton(f"Save {role.value} Profile")
            save_btn.clicked.connect(lambda _=False, r=role: self._save_profile(r))
            form.addRow(save_btn)
            self.profile_widgets[role] = {"exe": exe, "profile": profile, "url": url}
            layout.addWidget(box)

            row = self.db.get_profile(role)
            exe.setText(row["browser_exe"] or default_browser)
            profile.setText(row["profile_dir"])
            url.setText(row["url"])

        layout.addStretch(1)
        return page

    def _load_projects(self) -> None:
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        for row in self.db.list_projects():
            self.project_combo.addItem(row["name"], row["id"])
        self.project_combo.blockSignals(False)
        if self.project_combo.count() == 0:
            pid = self.db.create_project("Default Project")
            self.project_combo.addItem("Default Project", pid)
        self.project_combo.setCurrentIndex(0)
        self._project_changed(0)

    def _new_project(self) -> None:
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not name.strip():
            return
        try:
            pid = self.db.create_project(name)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Duplicate", "A project with that name already exists.")
            return
        self.project_combo.addItem(name.strip(), pid)
        self.project_combo.setCurrentIndex(self.project_combo.count() - 1)

    def _project_changed(self, index: int) -> None:
        if index < 0:
            return
        self.current_project_id = int(self.project_combo.itemData(index))
        self._load_tasks()

    def _load_tasks(self) -> None:
        self.task_list.blockSignals(True)
        self.task_list.clear()
        if self.current_project_id is not None:
            for task in self.db.list_tasks(self.current_project_id):
                item = QListWidgetItem(f"#{task.id}  {task.title}  [{task.status.value}]")
                item.setData(Qt.ItemDataRole.UserRole, task.id)
                self.task_list.addItem(item)
        self.task_list.blockSignals(False)
        if self.task_list.count() > 0:
            self.task_list.setCurrentRow(0)
            self._task_changed(self.task_list.currentItem(), None)
        else:
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
        self._load_tasks()
        for i in range(self.task_list.count()):
            if self.task_list.item(i).data(Qt.ItemDataRole.UserRole) == task_id:
                self.task_list.setCurrentRow(i)
                break

    def _task_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        self.current_task_id = int(current.data(Qt.ItemDataRole.UserRole))
        self._refresh_task_view()

    def _clear_task_view(self) -> None:
        self.current_role_label.setText("-")
        self.iteration_label.setText("-")
        self.task_status_label.setText("-")
        self.prompt_output.clear()
        self.result_input.clear()
        self.activity_table.setRowCount(0)
        for lab in self.agent_status_labels.values():
            lab.setText("Waiting")

    def _refresh_task_view(self) -> None:
        if self.current_task_id is None:
            self._clear_task_view()
            return
        task = self.db.get_task(self.current_task_id)
        self.current_role_label.setText(task.current_role.value)
        self.iteration_label.setText(str(task.iteration))
        self.task_status_label.setText(task.status.value)
        self.prompt_output.setPlainText(build_prompt(self.db, task) if task.status != TaskStatus.DONE else "Task completed.")
        self._update_outcome_choices(task.current_role, task.status)
        self._update_agent_statuses(task)
        self._load_activity()
        done = task.status == TaskStatus.DONE
        for w in [self.open_profile_btn, self.copy_prompt_btn, self.record_btn, self.next_btn]:
            w.setEnabled(not done)

    def _update_outcome_choices(self, role: Role, status: TaskStatus) -> None:
        self.outcome_combo.blockSignals(True)
        self.outcome_combo.clear()
        if status == TaskStatus.DONE:
            self.outcome_combo.addItem(Outcome.PASS.value)
        elif role == Role.DEVELOPER:
            self.outcome_combo.addItem(Outcome.SUBMITTED.value)
        else:
            self.outcome_combo.addItems([Outcome.PASS.value, Outcome.FAIL.value])
        self.outcome_combo.blockSignals(False)

    def _update_agent_statuses(self, task) -> None:
        for role, lab in self.agent_status_labels.items():
            lab.setText("Waiting")
        if task.status == TaskStatus.DONE:
            self.agent_status_labels[Role.DEVELOPER].setText("Passed")
            self.agent_status_labels[Role.REVIEWER].setText("Passed")
            self.agent_status_labels[Role.TESTER].setText("Done")
            return
        for role in Role:
            latest = self.db.latest_result(task.id, role)
            if latest:
                if latest.outcome == Outcome.FAIL:
                    self.agent_status_labels[role].setText("Failed")
                elif latest.outcome in (Outcome.PASS, Outcome.SUBMITTED):
                    self.agent_status_labels[role].setText("Passed")
        self.agent_status_labels[task.current_role].setText("Active")

    def _load_activity(self) -> None:
        assert self.current_task_id is not None
        rows = self.db.list_activity(self.current_task_id)
        self.activity_table.setRowCount(len(rows))
        for r_idx, rec in enumerate(rows):
            vals = [rec.created_at, str(rec.iteration), rec.role.value if rec.role else "-", rec.action, rec.detail]
            for c_idx, val in enumerate(vals):
                self.activity_table.setItem(r_idx, c_idx, QTableWidgetItem(val))

    def _browse_browser(self, role: Role) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select browser executable", "", "Executable (*.exe);;All files (*)")
        if path:
            widget = self.profile_widgets[role]["exe"]
            assert isinstance(widget, QLineEdit)
            widget.setText(path)

    def _save_profile(self, role: Role) -> None:
        w = self.profile_widgets[role]
        exe = w["exe"]
        profile = w["profile"]
        url = w["url"]
        assert isinstance(exe, QLineEdit) and isinstance(profile, QLineEdit) and isinstance(url, QLineEdit)
        self.db.save_profile(role, exe.text(), profile.text(), url.text())
        QMessageBox.information(self, "Saved", f"{role.value} browser profile saved locally.")

    def _open_current_profile(self) -> None:
        if self.current_task_id is None:
            return
        task = self.db.get_task(self.current_task_id)
        row = self.db.get_profile(task.current_role)
        try:
            open_profile(row["browser_exe"], row["profile_dir"], row["url"])
            self.db.add_activity(task.id, task.current_role, task.iteration, "Profile opened", row["profile_dir"] or "Default browser profile")
            self._load_activity()
        except Exception as exc:
            QMessageBox.critical(self, "Cannot open profile", str(exc))

    def _copy_prompt(self) -> None:
        text = self.prompt_output.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        if self.current_task_id is not None:
            task = self.db.get_task(self.current_task_id)
            self.db.add_activity(task.id, task.current_role, task.iteration, "Prompt copied", "Copied to clipboard")
            self._load_activity()

    def _paste_clipboard(self) -> None:
        self.result_input.setPlainText(QApplication.clipboard().text())

    def _record_result(self) -> bool:
        if self.current_task_id is None:
            return False
        task = self.db.get_task(self.current_task_id)
        text = self.result_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Missing result", "Paste or enter the agent result first.")
            return False
        outcome = Outcome(self.outcome_combo.currentText())
        self.db.add_result(task.id, task.current_role, task.iteration, outcome, text)
        self.db.add_activity(task.id, task.current_role, task.iteration, "Result recorded", outcome.value)
        self._load_activity()
        return True

    def _send_next(self) -> None:
        if self.current_task_id is None:
            return
        task = self.db.get_task(self.current_task_id)
        text = self.result_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Missing result", "Record an agent result before moving the workflow.")
            return
        outcome = Outcome(self.outcome_combo.currentText())

        latest = self.db.latest_result(task.id)
        same_result_already_recorded = (
            latest is not None
            and latest.role == task.current_role
            and latest.iteration == task.iteration
            and latest.outcome == outcome
            and latest.result_text == text
        )
        if not same_result_already_recorded:
            self.db.add_result(task.id, task.current_role, task.iteration, outcome, text)
            self.db.add_activity(task.id, task.current_role, task.iteration, "Result recorded", outcome.value)

        try:
            tr = transition(task.current_role, task.iteration, outcome)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid outcome", str(exc))
            return

        self.db.update_task_state(task.id, tr.next_role, tr.next_iteration, tr.task_status)
        self.db.add_activity(task.id, tr.next_role, tr.next_iteration, "State transition", tr.detail)
        self.result_input.clear()
        self._load_tasks()
        for i in range(self.task_list.count()):
            if self.task_list.item(i).data(Qt.ItemDataRole.UserRole) == task.id:
                self.task_list.setCurrentRow(i)
                break
        self._refresh_task_view()
        if tr.task_status == TaskStatus.DONE:
            QMessageBox.information(self, "Done", "Tester passed the task. Workflow is complete.")


def run() -> None:
    app = QApplication([])
    app.setApplicationName("AI Dev Team")
    win = MainWindow()
    win.show()
    app.exec()
