from __future__ import annotations


class GitHubService:
    """MVP extension point.

    Intentionally disabled in v0.1. A future version can add GitHub integration
    without changing the workflow/state-machine layer.
    """

    enabled = False

    def status(self) -> str:
        return "GitHub integration is not enabled in this MVP."
