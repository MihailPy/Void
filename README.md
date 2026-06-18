# Void

Void — локальный AI-помощник с deterministic core, tools, skills, memory, FastAPI backend и Web UI.

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

* Browser actions require approval.
* No cookies/session persistence by default.
* No login/form submission automation yet.
* Only http/https URLs are allowed.

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

Current project metadata version: Void v0.1.0. The API reports version `0.8.0`.

## Roadmap

- Interactive browser automation
- Git capability
- Better remote access
- More skills
- Web UI improvements

See [docs/roadmap.md](docs/roadmap.md) for the concise roadmap.
