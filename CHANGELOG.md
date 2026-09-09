# Changelog

## 1.1.0 — 2026-09-09

### Added
- In-window **Connections & permissions** review panel.
- Local approval gate for GitHub, Vercel and future external tools/plugins.
- Per-integration `Pending / Approved / Denied` decision state.
- Requested-purpose and requested-permissions display before approval.
- Provider connection checks using installed `gh` / `vercel` CLI without copying stored credentials.
- Provider links and a local integration audit trail.
- Reusable `PermissionBroker` so future integrations must call the same approval gate before access.
- Approval-gated GitHub and Vercel service boundaries.

### Privacy / authorization
- Approval inside AI Dev Team does not replace the provider's own OAuth/login flow.
- AI Dev Team does not store passwords, browser cookies, OAuth tokens or session tokens for integrations.
- A provider can be connected externally and still remain blocked until the user explicitly approves it inside AI Dev Team.

## 1.0.0 — 2026-09-09

First daily-usable local release.

### Added
- Developer → Reviewer → Tester state machine with fail loops and iteration tracking.
- Separate Chrome/Edge browser profile configuration per role.
- Browser profile discovery using non-secret Chromium profile metadata.
- One-click Copy + Open handoff and keyboard shortcuts.
- Role-specific prompt generation and persistent custom role instructions.
- PASS/FAIL response detection for Reviewer and Tester.
- Project metadata, task search/edit/delete/reopen controls.
- Results/handoff history and activity log.
- SQLite persistence with migration from the original MVP schema.
- Task Markdown export, project JSON export and SQLite backup.
- Optional auto-copy and auto-open after workflow transitions.
- Windows run/test/build/release scripts.
- Windows GitHub Actions CI with unit tests, PySide6 UI import smoke test and build artifact.

### Safety boundary
- No password, cookie or session-token storage.
- No automatic ChatGPT login, DOM scraping or restriction bypass.
