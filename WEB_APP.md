# AI Dev Team Web v2

Web-first version of AI Dev Team. It is a static browser app designed to deploy directly from this GitHub repository to Vercel or another static host.

## Why web-first

- Update code on GitHub and redeploy automatically; no repeated Windows ZIP downloads.
- Developer → Reviewer → Tester state machine remains available in the browser.
- Plugin Center is dynamic instead of being limited to GitHub/Vercel.
- Built-in integrations include GitHub, Vercel, Gmail, Google Calendar, Google Drive, Slack, Notion, Supabase, Firebase, OpenAI API and Gemini API.
- Custom integrations can be added from the UI.
- Task/result text is scanned for integration keywords. Matching integrations become Requested/Pending and must be Approved or Denied in Plugin Center.

## Data model

For the first web release, projects/tasks/history/approval state are stored in browser `localStorage` under `aiDevTeamWebV2`.

The app deliberately does not store passwords, cookies, OAuth/access tokens or ChatGPT session tokens.

Use Export/Import in the header to move or back up browser data.

## ChatGPT accounts

A hosted web page cannot force Windows to launch a specific Chrome profile. The Agents & Settings tab therefore stores:

- account/profile label
- ChatGPT URL
- a note describing which local Chrome profile should be used

A future optional Local Bridge can restore one-click local Chrome-profile launching without moving credentials into the web app.

## Plugin approval boundary

Approval in Plugin Center is AI Dev Team's local permission gate. It does not perform OAuth and does not grant provider access by itself. When a real provider connection is implemented, it must still check the local approval state first and then use the provider's normal OAuth/connection flow.

## Deploy to Vercel

The repository root contains `index.html`, `styles.css`, `app-1.js`, `app-2.js`, `app-3.js` and `vercel.json`. No npm install or build command is required.

Connect this GitHub repository to Vercel once. After that, pushes to `main` can redeploy automatically.

## Desktop version

The existing Python/PySide6 desktop source remains in the repository for local-browser-profile features and as a fallback. The web app does not delete or overwrite desktop data.
