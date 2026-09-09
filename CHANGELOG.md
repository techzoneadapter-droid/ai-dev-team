# Changelog

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
