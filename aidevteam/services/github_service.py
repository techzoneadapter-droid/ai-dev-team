from __future__ import annotations


class GitHubService:
    """Reserved integration boundary for a future authenticated GitHub workflow.

    The core app does not require GitHub credentials. Keeping this service isolated
    lets future versions add repository/PR operations without coupling them to
    ChatGPT browser profiles or the workflow state machine.
    """

    enabled = False

    def status(self) -> str:
        return "GitHub automation is optional and not enabled in v1.0."
