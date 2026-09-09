# AI Dev Team — MVP

A small local Windows desktop app for coordinating three human-controlled ChatGPT browser profiles:

- Developer
- Reviewer
- Tester

The app implements this workflow:

`Developer -> Reviewer -> (Fail -> Developer / Pass -> Tester) -> (Fail -> Developer / Pass -> Done)`

## Safety / login model

This MVP does **not** store or read:

- email/password
- cookies
- session tokens
- ChatGPT credentials

It also does not attempt to bypass ChatGPT restrictions, anti-bot checks, rate limits, or login controls.

Browser support is intentionally limited to launching a configured Chrome/Edge executable with a configured profile directory and opening `https://chatgpt.com/`. Sending prompts and collecting results remains user-controlled through copy/paste.

## Features

- 3 fixed workflow roles: Developer, Reviewer, Tester
- Separate browser profile configuration for each role
- Overall task input
- Automatic role-specific prompt generation
- State machine with pass/fail loops
- Iteration counter
- Per-agent status snapshot
- Activity log
- Open Profile button
- Copy Prompt button
- Paste Clipboard / Record Result
- Send to Next Role
- Local projects/tasks/history using SQLite
- GitHub service stub for future expansion

## Windows prerequisites

- Windows 10/11
- Python 3.11+ recommended
- Chrome or Edge

## Run from source

1. Extract the project.
2. Double-click `run.bat`.
3. On first launch, dependencies are installed into `.venv`.
4. Open the **Browser Profiles** tab.
5. Set a browser executable and profile directory for each role.

Typical Chrome executable:

`C:\Program Files\Google\Chrome\Application\chrome.exe`

Typical Edge executable:

`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`

Typical profile directory values:

- `Default`
- `Profile 1`
- `Profile 2`
- `Profile 3`

To find the exact Chrome profile directory, open the intended Chrome profile and visit `chrome://version`, then inspect **Profile Path**. The last folder name is usually what you enter into AI Dev Team.

## Normal workflow

1. Create/select a project.
2. Enter task title + overall task and click **Start Task**.
3. Developer becomes Active.
4. Click **Open Profile**, then **Copy Prompt**.
5. Paste the prompt into the intended ChatGPT browser window yourself.
6. Paste the response back into AI Dev Team.
7. For Developer, outcome is `Submitted`; click **Send to Next Role**.
8. Reviewer uses `Pass` or `Fail`.
9. Reviewer Fail increases iteration and returns to Developer.
10. Reviewer Pass advances to Tester.
11. Tester Fail increases iteration and returns to Developer.
12. Tester Pass marks the task Done.

## Local data location

SQLite is stored locally at:

`%LOCALAPPDATA%\AI Dev Team\aidevteam.db`

No ChatGPT session data is written to the database.

## Build Windows app

Double-click:

`build.bat`

PyInstaller will create:

`dist\AI Dev Team\AI Dev Team.exe`

The default build is a folder-based executable because it is generally easier to troubleshoot than a single-file build.

## GitHub extension point

`aidevteam/services/github_service.py` is intentionally a stub in this MVP. A future release can add repository selection, branch/worktree handling, diff handoff, and commit/test status without changing the state machine.

## Limitations of v0.1

- No automatic ChatGPT login
- No automatic prompt injection or Send-button clicking
- No browser DOM scraping
- No cookie/session import
- No ChatGPT restriction bypass
- No automatic GitHub operations
- Status parsing is manual via the Outcome selector rather than trusting free-form text

These limits are deliberate so the app remains local, transparent, and human-in-the-loop.
