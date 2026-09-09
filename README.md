# AI Dev Team

**AI Dev Team** is a local Windows desktop app that coordinates three human-controlled ChatGPT browser profiles in a software workflow:

`Developer → Reviewer → (FAIL → Developer / PASS → Tester) → (FAIL → Developer / PASS → Done)`

Current version: **1.0.0**

## What v1.0 includes

- Developer / Reviewer / Tester state machine with iteration counter
- Separate Chrome/Edge profile per role
- One-click **Copy + Open** handoff
- Automatic role-specific prompt generation
- Custom persistent instructions per role
- Reviewer/Tester `PASS` / `FAIL` detection from the first response line
- Project metadata: notes, local workspace and optional GitHub repository URL
- Task creation, editing, deletion, reopening and search
- Agent status indicators
- Full results/handoff history
- Activity log
- Local SQLite persistence
- Markdown export for an individual task
- Portable JSON export for a project
- SQLite database backup
- Optional copy/open behavior after a workflow transition
- Browser profile discovery for Chrome/Edge without reading cookies or session data
- Windows build and release scripts
- Migration support from the original MVP database
- Unit tests for workflow, persistence, migrations, exports and browser launch command construction

## Privacy / browser boundary

AI Dev Team does **not** store or read:

- ChatGPT email/password
- cookies
- session tokens
- authentication headers

It does not automate ChatGPT login, scrape the ChatGPT DOM, import sessions, bypass anti-bot controls, or bypass usage/rate limits.

Browser assistance is intentionally limited to opening a configured Chrome/Edge profile and URL. Prompt sending and result collection remain user-controlled through copy/paste.

## Windows requirements

- Windows 10 or Windows 11
- Python 3.11+ recommended
- Google Chrome or Microsoft Edge

## Run from source

1. Clone/download this repository.
2. Double-click `run.bat`.
3. On first launch, a local `.venv` is created and dependencies are installed.
4. Go to **Browser Profiles** and configure Developer, Reviewer and Tester.
5. Create a project and start a task.

Typical browser paths:

```text
C:\Program Files\Google\Chrome\Application\chrome.exe
C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
```

Typical profile directories:

```text
Default
Profile 1
Profile 2
Profile 3
```

You can click **Detect profiles** to list Chrome/Edge profile names. The discovery code reads only Chromium's `Local State` profile-name metadata; it does not read cookies or login sessions.

## Daily workflow

1. Start a task. Developer becomes Active.
2. Click **Copy + Open**.
3. Paste the prompt into the Developer ChatGPT profile.
4. Paste Developer's response into AI Dev Team and click **Record + Send to Next Role**.
5. Reviewer becomes Active. Repeat the handoff.
6. Reviewer begins with `PASS` or `FAIL`.
   - `FAIL` creates a new iteration and returns to Developer.
   - `PASS` advances to Tester.
7. Tester begins with `PASS` or `FAIL`.
   - `FAIL` creates a new iteration and returns to Developer.
   - `PASS` marks the task Done.
8. A Done task can be reopened later as a new Developer iteration.

Keyboard shortcuts:

- `Ctrl+Shift+C` — copy current prompt
- `Ctrl+Shift+O` — open current profile
- `Ctrl+Enter` — record result and send to next role

## Local data

The default database is stored at:

```text
%LOCALAPPDATA%\AI Dev Team\aidevteam.db
```

Use **Settings → Backup Database** to create a safe SQLite copy.

## Tests

Run:

```text
test.bat
```

or:

```bash
python -m unittest discover -s tests -v
```

## Build a Windows app

Run:

```text
build.bat
```

Output:

```text
dist\AI Dev Team\AI Dev Team.exe
```

For a distributable ZIP, run:

```text
release.bat
```

## GitHub extension point

`aidevteam/services/github_service.py` remains intentionally isolated as an extension point. A later version can add local repository status, diff/commit handoff or authenticated GitHub operations without coupling them to the core workflow or browser sessions.

## Project structure

```text
main.py
requirements.txt
run.bat
build.bat
release.bat
test.bat

aidevteam/
  db.py
  exporter.py
  models.py
  prompts.py
  state_machine.py
  ui.py
  version.py
  services/
    browser_service.py
    github_service.py

tests/
  test_core.py
  test_migrations.py
```
