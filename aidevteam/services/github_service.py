from __future__ import annotations

from aidevteam.integrations import PermissionBroker


class GitHubService:
    """Approval-gated boundary for future GitHub automation.

    The service never receives or stores GitHub passwords, cookies or tokens.
    Before any future repository mutation is allowed, the local permission broker
    must show GitHub as Approved in the main AI Dev Team window.
    """

    def __init__(self, db=None) -> None:
        self.db = db

    def status(self) -> str:
        if self.db is None:
            return "GitHub integration is optional; no database/approval context is attached."
        broker = PermissionBroker(self.db)
        decision = broker.decision("github")
        connection = broker.connection_status("github")
        return f"GitHub approval: {decision}. Connection: {connection}."

    def require_ready(self) -> None:
        if self.db is None:
            raise PermissionError("GitHub integration has no approval context.")
        PermissionBroker(self.db).require_approval("github")
