from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class IntegrationSpec:
    key: str
    name: str
    purpose: str
    permissions: tuple[str, ...]
    provider_url: str
    cli_command: str
    check_args: tuple[str, ...]


INTEGRATIONS: tuple[IntegrationSpec, ...] = (
    IntegrationSpec(
        key="github",
        name="GitHub",
        purpose="Source control, repository files, branches, commits and pull-request workflows.",
        permissions=(
            "Read repository metadata",
            "Read project files",
            "Write repository files/commits only after explicit approval",
            "Create/update pull requests only after explicit approval",
        ),
        provider_url="https://github.com/settings/installations",
        cli_command="gh",
        check_args=("auth", "status"),
    ),
    IntegrationSpec(
        key="vercel",
        name="Vercel",
        purpose="Optional project/deployment integration for apps that need preview or production builds.",
        permissions=(
            "Read project/deployment metadata",
            "Read deployment status/log summaries",
            "Create a deployment only after explicit approval",
        ),
        provider_url="https://vercel.com/account",
        cli_command="vercel",
        check_args=("whoami",),
    ),
)


class PermissionBroker:
    """Local approval gate for external integrations.

    Decisions and non-secret status text are stored through the app's existing
    settings table. Credentials, cookies and OAuth/session tokens are never
    stored by this broker.
    """

    def __init__(self, db) -> None:
        self.db = db
        self.ensure_requests()

    def ensure_requests(self) -> None:
        for spec in INTEGRATIONS:
            requested_key = f"integration.{spec.key}.requested"
            if not self.db.get_setting(requested_key, ""):
                self.db.set_setting(requested_key, "true")
            decision_key = f"integration.{spec.key}.decision"
            if not self.db.get_setting(decision_key, ""):
                self.db.set_setting(decision_key, "pending")

    def request(
        self,
        key: str,
        *,
        purpose: str | None = None,
        permissions: Iterable[str] | None = None,
    ) -> None:
        """Register or refresh a request from a future plugin/service."""
        self.db.set_setting(f"integration.{key}.requested", "true")
        self.db.set_setting(f"integration.{key}.decision", "pending")
        if purpose is not None:
            self.db.set_setting(f"integration.{key}.purpose_override", purpose)
        if permissions is not None:
            self.db.set_setting(
                f"integration.{key}.permissions_override",
                json.dumps(list(permissions), ensure_ascii=False),
            )
        self._audit(key, "requested")

    def decision(self, key: str) -> str:
        value = self.db.get_setting(f"integration.{key}.decision", "pending").strip().lower()
        return value if value in {"pending", "approved", "denied"} else "pending"

    def set_decision(self, key: str, decision: str) -> None:
        decision = decision.strip().lower()
        if decision not in {"pending", "approved", "denied"}:
            raise ValueError(f"Invalid integration decision: {decision}")
        self.db.set_setting(f"integration.{key}.decision", decision)
        self._audit(key, decision)

    def require_approval(self, key: str) -> None:
        if self.decision(key) != "approved":
            raise PermissionError(
                f"{key} integration is not approved. Review Connections & permissions in AI Dev Team first."
            )

    def connection_status(self, key: str) -> str:
        return self.db.get_setting(f"integration.{key}.connection_status", "Not checked")

    def set_connection_status(self, key: str, value: str) -> None:
        clean = " ".join(str(value).split())[:240] or "Unknown"
        self.db.set_setting(f"integration.{key}.connection_status", clean)
        self.db.set_setting(
            f"integration.{key}.connection_checked_at",
            datetime.now().isoformat(timespec="seconds"),
        )

    def check_connection(self, spec: IntegrationSpec) -> str:
        executable = shutil.which(spec.cli_command)
        if not executable:
            status = f"{spec.cli_command} CLI not installed"
            self.set_connection_status(spec.key, status)
            return status
        try:
            completed = subprocess.run(
                [executable, *spec.check_args],
                capture_output=True,
                text=True,
                timeout=12,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            status = f"Check failed: {type(exc).__name__}"
            self.set_connection_status(spec.key, status)
            return status

        combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
        first_line = next((line.strip() for line in combined.splitlines() if line.strip()), "")
        if completed.returncode == 0:
            status = "Connected"
            if first_line and len(first_line) <= 100:
                status += f" — {first_line}"
        else:
            status = "Not connected"
            if first_line and len(first_line) <= 100:
                status += f" — {first_line}"
        self.set_connection_status(spec.key, status)
        return status

    def _audit(self, key: str, action: str) -> None:
        raw = self.db.get_setting("integration.audit", "[]")
        try:
            items = json.loads(raw)
            if not isinstance(items, list):
                items = []
        except json.JSONDecodeError:
            items = []
        items.append(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "integration": key,
                "action": action,
            }
        )
        self.db.set_setting("integration.audit", json.dumps(items[-100:], ensure_ascii=False))


class IntegrationReviewPanel(QGroupBox):
    def __init__(self, parent: QWidget, db) -> None:
        super().__init__("Connections & permissions", parent)
        self.db = db
        self.broker = PermissionBroker(db)
        self.setMaximumHeight(240)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "External tools/plugins must be reviewed here before AI Dev Team may use them. "
            "Approval is a local permission gate; provider sign-in is separate. No passwords, cookies or access tokens are stored here."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#475467;")
        layout.addWidget(intro)

        self.summary = QLabel("")
        self.summary.setStyleSheet("font-weight:600;")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Provider", "Why", "Requested permissions", "Approval", "Connection"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(92)
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        approve = QPushButton("Approve selected")
        approve.setObjectName("primary")
        approve.clicked.connect(lambda: self._set_selected("approved"))
        actions.addWidget(approve)
        deny = QPushButton("Deny selected")
        deny.clicked.connect(lambda: self._set_selected("denied"))
        actions.addWidget(deny)
        reset = QPushButton("Reset to Pending")
        reset.clicked.connect(lambda: self._set_selected("pending"))
        actions.addWidget(reset)
        check = QPushButton("Check connection")
        check.clicked.connect(self._check_selected)
        actions.addWidget(check)
        provider = QPushButton("Open provider")
        provider.clicked.connect(self._open_selected_provider)
        actions.addWidget(provider)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.refresh()

    def _selected_spec(self) -> IntegrationSpec | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(INTEGRATIONS):
            return None
        key_item = self.table.item(row, 0)
        if key_item is None:
            return None
        key = key_item.data(256)
        return next((spec for spec in INTEGRATIONS if spec.key == key), None)

    def _set_selected(self, decision: str) -> None:
        spec = self._selected_spec()
        if spec is None:
            QMessageBox.information(self, "Select an integration", "Select GitHub, Vercel, or another integration first.")
            return
        if decision == "approved":
            permissions = "\n• " + "\n• ".join(spec.permissions)
            answer = QMessageBox.question(
                self,
                f"Approve {spec.name}?",
                f"AI Dev Team may use {spec.name} only for the following requested permissions:{permissions}\n\n"
                "This does not store provider credentials and does not bypass the provider's own authorization flow.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.broker.set_decision(spec.key, decision)
        self.refresh(select_key=spec.key)

    def _check_selected(self) -> None:
        spec = self._selected_spec()
        if spec is None:
            QMessageBox.information(self, "Select an integration", "Select an integration first.")
            return
        status = self.broker.check_connection(spec)
        self.refresh(select_key=spec.key)
        QMessageBox.information(
            self,
            f"{spec.name} connection",
            f"{status}\n\nAI Dev Team checks the provider CLI only. It does not read or copy stored tokens.",
        )

    def _open_selected_provider(self) -> None:
        spec = self._selected_spec()
        if spec is None:
            QMessageBox.information(self, "Select an integration", "Select an integration first.")
            return
        QDesktopServices.openUrl(QUrl(spec.provider_url))

    def refresh(self, select_key: str | None = None) -> None:
        self.table.setRowCount(len(INTEGRATIONS))
        pending = approved = denied = 0
        select_row = -1
        for row, spec in enumerate(INTEGRATIONS):
            decision = self.broker.decision(spec.key)
            if decision == "pending":
                pending += 1
            elif decision == "approved":
                approved += 1
            else:
                denied += 1
            provider = QTableWidgetItem(spec.name)
            provider.setData(256, spec.key)
            self.table.setItem(row, 0, provider)
            self.table.setItem(row, 1, QTableWidgetItem(spec.purpose))
            self.table.setItem(row, 2, QTableWidgetItem(" • ".join(spec.permissions)))
            approval_text = {"pending": "Pending", "approved": "Approved", "denied": "Denied"}[decision]
            approval_item = QTableWidgetItem(approval_text)
            if decision == "approved":
                approval_item.setToolTip("Locally approved. Provider authentication may still be required.")
            elif decision == "denied":
                approval_item.setToolTip("Blocked. Integration code must not run until approval changes.")
            self.table.setItem(row, 3, approval_item)
            self.table.setItem(row, 4, QTableWidgetItem(self.broker.connection_status(spec.key)))
            if select_key == spec.key:
                select_row = row
        self.summary.setText(f"Pending: {pending}   •   Approved: {approved}   •   Denied: {denied}")
        if select_row >= 0:
            self.table.selectRow(select_row)
        elif self.table.rowCount() and self.table.currentRow() < 0:
            self.table.selectRow(0)


def install_integration_review(window) -> IntegrationReviewPanel:
    """Insert the approval panel directly into the existing main window."""
    panel = IntegrationReviewPanel(window, window.db)
    central = window.centralWidget()
    layout = central.layout() if central is not None else None
    if layout is None:
        raise RuntimeError("Main window central layout is unavailable")
    tabs = getattr(window, "tabs", None)
    index = layout.indexOf(tabs) if tabs is not None else -1
    if index >= 0:
        layout.insertWidget(index, panel)
    else:
        layout.addWidget(panel)
    window.integration_review_panel = panel
    return panel
