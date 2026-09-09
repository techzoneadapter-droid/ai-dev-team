from __future__ import annotations

from aidevteam.integrations import PermissionBroker


class VercelService:
    """Approval-gated boundary for optional Vercel deployment workflows."""

    def __init__(self, db=None) -> None:
        self.db = db

    def status(self) -> str:
        if self.db is None:
            return "Vercel integration is optional; no database/approval context is attached."
        broker = PermissionBroker(self.db)
        decision = broker.decision("vercel")
        connection = broker.connection_status("vercel")
        return f"Vercel approval: {decision}. Connection: {connection}."

    def require_ready(self) -> None:
        if self.db is None:
            raise PermissionError("Vercel integration has no approval context.")
        PermissionBroker(self.db).require_approval("vercel")
