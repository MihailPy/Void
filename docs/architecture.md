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
- Browser Capability: approval-gated Playwright tools for http/https page title, text extraction, links, screenshots, and read-only page inspection.
- Git Capability: safe Git status, diff, log, current branch, commit message suggestion, and approval-gated commit.
- Project Context: JSON-backed current project identity and known project metadata.

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
- Project context: known projects and the current project.
- Capabilities memory: installed, requested, and rejected capability records.
- Scheduled tasks: JSON-backed task storage.

Memory files live under `memory/` and runtime package defaults live under `void/memory/`.

## Project Context

- Project context is stored in `memory/projects.json`.
- The file records `current_project` plus a simple list of project records.
- Project records include `id`, `name`, `aliases`, `root_path`, `repo_url`, and command keys.
- Aliases let the router, API, and tools resolve names like `Void` or `MihailPy/Void`.
- Void does not auto-scan the disk for projects and does not use a database.

## Project Commands

- Project commands live in `memory/projects.json` under each project's `commands` object.
- Commands are predefined per project and are executed only by command key.
- Void does not accept arbitrary shell command text from users.
- Command execution requires approval through the standard permission layer.
- Approved commands run from the current project's safe root path.
- stdout, stderr, return code, duration, command, cwd, and project identity are captured.
- Visible terminal mode is not implemented yet.
- Streaming logs, background jobs, and interactive stdin are not implemented yet.

## Permission Layer

- Approvals are required for protected state-changing actions.
- Pending approvals are stored in `memory/pending_approvals.json`.
- CLI and API can approve or reject pending actions.
- The Tool Registry enforces approval requirements before executing protected tools.

## Scheduler

- Scheduled tasks storage is JSON-backed.
- Scheduler tools create, list, run, enable, disable, and delete tasks.
- The scheduler worker starts with FastAPI when enabled and periodically runs due tasks through the standard agent.

## Browser Capability

- Browser tools use Playwright with Chromium.
- Stateless browser actions open a fresh background browser for each approved action and close it afterward.
- Managed headless sessions keep one Playwright page alive in the API process.
- Managed visible sessions open a Void-owned visible browser window and are not attached to the user's personal browser.
- Browser actions, session opens, session closes, and session interactions require approval. Session listing and status checks are read-only.
- URL handling allows only `http` and `https`; `file`, `javascript`, and `data` schemes are blocked.
- Screenshots are limited to `workspace/screenshots/`.
- Browser task is read-only and does not click, log in, fill forms, submit data, run user-provided JavaScript, or persist sessions.
- Limitations: no attach to existing personal Chrome, no persistent cookies or profile by default, no login automation workflow, no arbitrary JavaScript execution, session state is in-memory and lost on API restart, and the session manager allows at most 3 open sessions.

## Git Capability

- Read-only Git tools expose status, diff, staged diff, log, and current branch.
- Commit message suggestions are deterministic and based on status plus staged or unstaged diff.
- `git_commit` requires approval and never runs `git add`.
- Git push, pull, reset, checkout, switch, merge, rebase, clean, remote, and config are blocked.

## Safety

- File tools use safe project paths.
- Common generated and cache directories are ignored where appropriate.
- Protected actions require approval before execution.
- API token auth protects endpoints when `VOID_API_TOKEN` is set.
- Future interactive browser automation should be added as a separate capability with explicit approvals and tighter action controls.
- Advanced git workflows should be added only with stronger approval controls.
