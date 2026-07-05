# Void

Void — локальный AI-помощник с deterministic core, tools, skills, memory, FastAPI backend и Web UI.

## Version

Current version: **Void v1.4.0**

## Features

- CLI interface
- FastAPI backend
- Web UI
- Tool Registry
- Router
- Skill System
- Permission Layer / Approvals
- Capability System
- Task Scheduler
- Scheduler Worker
- Browser Capability
- Git Capability
- Memory layer
- LLM fallback through LM Studio / OpenAI-compatible API

## Project Structure

```text
void/
  core/
  api/
  tools/
  skills/
  memory/
web/
memory/
workspace/
docs/
```

## Requirements

- Python 3.11+
- Node.js 18+
- npm
- LM Studio or OpenAI-compatible API for fallback

## Environment

Copy `.env.example` to `.env` for local configuration:

```bash
cp .env.example .env
```

Variables:

- `VOID_API_TOKEN` — optional API token. If unset, the backend runs in local development mode without auth.
- `VOID_SCHEDULER_WORKER_ENABLED` — enables or disables the scheduler worker. Defaults to `true`.
- `VOID_SCHEDULER_WORKER_INTERVAL` — scheduler worker polling interval in seconds. Defaults to `60`.
- `VITE_VOID_API_URL` — Web UI backend URL. Defaults to `http://127.0.0.1:8000`.

## Run CLI

```bash
make cli
```

or:

```bash
python -m void.main
```

## Run API

```bash
make api
```

or:

```bash
python -m void.api.server
```

Useful API URLs:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

## Run Web UI

```bash
make web-install
make web
```

The Vite dev server runs on `http://localhost:5173` by default.

## Browser Capability

Install browser runtime after installing Python dependencies:

```bash
python -m playwright install chromium
```

Examples:

CLI:

```text
Получи текст со страницы https://example.com
Сделай скриншот https://example.com
Покажи ссылки на странице https://example.com
```

Important:

- Browser actions require approval.
- Only http/https URLs are allowed.

### Browser Modes

- Stateless browser actions: each approved title, text, links, screenshot, task, or selector action opens a fresh background browser and closes it when the action finishes.
- Managed headless sessions: approved session opens keep one Playwright page alive in the API process without showing a browser window.
- Managed visible sessions: approved session opens launch a Void-owned visible browser window. This is not attached to your personal Chrome or browser profile.
- Approval requirements: stateless browser actions, opening sessions, closing sessions, and session interactions require approval. Listing sessions and checking session status are read-only.
- Limits: attach-to-existing-browser is not implemented, personal Chrome is not connected, cookies and profiles are not persisted by default, login automation workflows are not provided, arbitrary JavaScript execution is not exposed, session state is in-memory and lost on API restart, and at most 3 sessions may be open.

## Project Link Actions

Project repository links are read from `memory/projects.json` as configured
`repo_url` values. Opening a project repo creates a managed Void browser
session, defaults to visible mode, and requires approval before the browser is
opened.

This does not attach to personal Chrome, does not use persistent browser
profiles, and does not open arbitrary user-provided URLs.

## Assistant Flows

Void assistant flows are deterministic-first and tools-first. The router maps
supported project and command requests to registered tools, asks for approval
before state-changing actions, and uses the LLM only as a fallback.

Supported project flows:

- Show the current project.
- Switch the current project.
- Open a configured project repository in a managed browser session.

Supported command flows:

- List configured project commands.
- Run configured project commands after approval.
- Run configured project commands in a visible terminal after approval.

Supported clarification flows:

- Missing project selection.
- Missing command selection.

Supported approval flows:

- State-changing actions require approval before execution.
- Approved actions return an inline final result, such as a command result,
  browser session result, or project context update.

Supported browser flows:

- Opening a project repo creates a managed Void browser session.
- Visible sessions open a Void-owned browser window and are not attached to a
  personal browser profile.

Limitations:

- No arbitrary shell execution.
- No planner.
- No autonomous multi-step execution.
- No attach-to-personal-browser support.

## Git Capability

Examples:

CLI:

```text
git status
покажи diff
какой commit написать
сделай commit с сообщением "Void v1.4: Git Capability"
```

Notes:

- git_commit requires approval.
- git add is not automatic.
- push/pull/reset/checkout/merge are not supported for safety.

Web UI:

Git tab.

## Clarification Flow

Void can pause deterministic actions when a supported required input is missing,
store one pending clarification, and resume the original action after the next
answer.

Storage:

- Pending clarification state is JSON in `memory/pending_clarification.json`.
- v1 supports a single active clarification at a time.
- Creating a new clarification replaces the previous pending one.
- A resolved clarification is cleared after the answer is mapped to a resumed action.

Supported v1 cases:

- `open project on github` asks which project to open.
- `run project command` asks which configured command key to run.
- `run command in terminal` asks which configured command key to run visibly.
- `switch project` asks which project to switch to.

API endpoints:

```text
GET  /clarification
POST /clarification/respond
```

Limits:

- Clarification Flow is not a planner.
- It is not autonomous multi-step reasoning.
- It does not support multiple simultaneous clarifications.
- It only covers the deterministic missing-input cases listed above.

## Auth

If `VOID_API_TOKEN` is not set, Void runs in local dev mode and protected API endpoints do not require auth.

If `VOID_API_TOKEN` is set, protected endpoints require a bearer token:

```bash
curl -H "Authorization: Bearer change-me" http://127.0.0.1:8000/tasks
```

Do not expose the API directly to the public internet without a trusted access layer such as VPN, Tailscale, or an HTTPS reverse proxy.

## Scheduler

Void stores scheduled tasks in `memory/scheduled_tasks.json`. Tasks can be created, listed, enabled, disabled, deleted, and run manually.

The scheduler worker starts with the FastAPI backend when `VOID_SCHEDULER_WORKER_ENABLED=true`. It polls due tasks every `VOID_SCHEDULER_WORKER_INTERVAL` seconds and runs them through the standard agent.

CLI commands:

```text
/tasks
/run-task <id>
/enable-task <id>
/disable-task <id>
/delete-task <id>
```

API endpoints:

```text
GET  /tasks
POST /tasks
POST /tasks/{task_id}/run
POST /tasks/{task_id}/enable
POST /tasks/{task_id}/disable
DELETE /tasks/{task_id}
GET  /scheduler/status
POST /scheduler/run-once
```

State-changing task actions create approvals. Approve them through the Web UI Approvals tab or with:

```text
POST /approvals/{approval_id}/approve
```

## Useful Commands

```bash
make check
make clean
make cli
make api
make web
```

## Development Status

Current project metadata version: Void v1.4.0.

## Roadmap

- Interactive browser automation
- Advanced git workflows with stronger approval controls
- Better remote access
- More skills
- Web UI improvements

See [docs/roadmap.md](docs/roadmap.md) for the concise roadmap.
