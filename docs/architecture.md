# Architecture

Void is organized around a deterministic local agent runtime. The CLI, API, Web UI, scheduler, tools, skills, permissions, and memory all use the same core execution path.

## User Interface Layer

- CLI: interactive terminal interface in `void/main.py`.
- Web UI: React/Vite frontend in `web/`.
- FastAPI: backend API in `void/api/`.

## Agent Core

- Router: deterministic intent routing for known requests.
- Skill Registry: deterministic skill matching and execution.
- Tool Registry: safe dispatch for executable tools.
- LLM fallback: LM Studio or another OpenAI-compatible API is used when deterministic routing and skills do not handle a request.

## Execution Order

1. Router
2. Skill Registry
3. Tool Registry
4. LLM fallback

The agent first tries a high-confidence router action. If that does not match, it tries deterministic skills. If neither path resolves the request, it asks the LLM fallback for an action JSON and executes the selected tool through the Tool Registry.

## Memory

- Session memory: request and action history.
- Facts memory: durable user or environment facts.
- Project memory: project-level notes and summaries.
- Capabilities memory: installed, requested, and rejected capability records.
- Scheduled tasks: JSON-backed task storage.

Memory files live under `memory/` and runtime package defaults live under `void/memory/`.

## Permission Layer

- Approvals are required for protected state-changing actions.
- Pending approvals are stored in `memory/pending_approvals.json`.
- CLI and API can approve or reject pending actions.
- The Tool Registry enforces approval requirements before executing protected tools.

## Scheduler

- Scheduled tasks storage is JSON-backed.
- Scheduler tools create, list, run, enable, disable, and delete tasks.
- The scheduler worker starts with FastAPI when enabled and periodically runs due tasks through the standard agent.

## Safety

- File tools use safe project paths.
- Common generated and cache directories are ignored where appropriate.
- Protected actions require approval before execution.
- API token auth protects endpoints when `VOID_API_TOKEN` is set.
