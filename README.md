# Void

Void — локальный AI-помощник с deterministic core, tools, skills, memory, FastAPI backend и Web UI.

## Version

The release version is centralized in `void/__version__.py`.

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
- Browser Interactive
- Managed Browser Sessions
- Project Context
- Project Commands
- Project Workspace
- Project Link Actions
- Clarification Flow
- Visible Terminal Runner
- Git Capability
- Activity History
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

## Project Workspace

Projects may define an optional `workspace` block in `memory/projects.json`.
The workspace describes how a user's project workspace should be opened without
adding a database, planner, or environment automation layer.

Example:

```json
{
  "id": "void",
  "name": "Void",
  "root_path": ".",
  "repo_url": "https://github.com/MihailPy/Void",
  "workspace": {
    "terminal": {
      "app": "terminal",
      "command": "cd {root} && nvim ."
    },
    "browser": {
      "app": "default"
    },
    "file_manager": {
      "app": "Finder"
    }
  }
}
```

Supported workspace targets:

- `terminal`: launches the configured `workspace.terminal.command` in the
  existing visible terminal runner after replacing `{root}` with the project
  root. Only commands stored in project configuration are eligible.
- `finder`: opens the project root with the platform file manager (`open`,
  `explorer`, or `xdg-open`).
- `github`: opens the configured project repository URL.
- `browser`: opens the configured project repository URL and may use
  `workspace.browser.app` on supported platforms.
- `editor`: reserved for future implementation. Void returns
  `Editor workspace is not implemented yet.`

Workspace opens require approval and are logged as `workspace_open` activities.
Replay support replays the same `open_project_workspace` target through the
normal approval flow.

Example commands:

```text
Open workspace
Open project in Finder
Open current project on GitHub
Open project in browser
Run project command verify
Покажи команды проекта
Открой проект в Finder
Открой текущий проект на GitHub
Используй профиль Development
```

### Workspace Preferences

Workspace preferences can be viewed and edited through Void without manually
editing `memory/projects.json`. Reads do not require approval. Updates require
approval and are saved back through Project Context JSON persistence.

Editable fields:

- `workspace.terminal.app`: `terminal`, `iterm`, or `iterm2`.
- `workspace.terminal.command`: non-empty and must contain `{root}`.
- `workspace.terminal.reuse_existing`: accepts `true`, `false`, `yes`, `no`,
  `1`, `0`, `on`, or `off`, and is saved as `true` or `false`.
- `workspace.terminal.open_mode`: `tab` or `window`.
- `workspace.terminal.profile`: non-empty string.
- `workspace.terminal.window_bounds`: `left,top,right,bottom`, four integers
  with `left < right` and `top < bottom`.
- `workspace.browser.app`: any non-empty string, for example `Safari`,
  `Google Chrome`, `Arc`, `Zen`, `Default`, or `Managed`.
- `workspace.file_manager.app`: any non-empty string.

Only these fields are editable. Unknown workspace keys are preserved for
backward compatibility. Preference updates are logged as
`workspace_preferences_update` activities and are not replayable.

Preference saves are atomic batches: one Save request creates one approval, all
values are validated before persistence, and a rejected approval leaves
`memory/projects.json` unchanged.

## Managing Projects

The Projects tab in the Web UI is the Project Registry editor for
`memory/projects.json`. Users can create, edit, duplicate, delete, and select
the current project without manually editing JSON.

Each project entry keeps the existing JSON shape:

- `id`
- `name`
- `aliases`
- `root_path`
- `repo_url`
- `commands`
- `workspace`

The editor supports:

- General fields: ID, name, root path, and repository URL.
- Aliases: add, remove, and reorder aliases.
- Commands: add, edit, remove, and reorder command keys and command strings.
- Workspace: the same editable workspace preference fields documented above.

Create, save, and delete are state-changing operations. They validate first,
then create one approval. Approving performs one JSON persistence write and one
Activity History entry. Rejecting leaves the registry unchanged.

Activity types:

- `project_create`
- `project_update`
- `project_delete`
- `project_duplicate`

Duplicating a project creates an editable draft named `Original Copy` with a
generated unique ID. The draft is not written until Save is approved.

Deleting the last project is rejected. Deleting the current project requires
explicit confirmation; after approval, Void switches to another remaining
project automatically.

### Exporting Projects

Project exports are portable JSON and do not require approval. Export supports
the current project, a selected project, or all projects. The output shape is:

```json
{
  "version": 1,
  "projects": [
    {
      "id": "void",
      "name": "Void",
      "aliases": ["void"],
      "root_path": ".",
      "repo_url": "https://github.com/MihailPy/Void",
      "commands": {},
      "workspace": {}
    }
  ]
}
```

Export preserves the project records as stored by the registry, including
unknown fields. Export logs a read-only `project_export` Activity History event.

### Importing Projects

Project import accepts a single project object, a list of projects, or an object
with a `projects` array. Users can paste JSON in the Web UI or send JSON through
the API/tool layer.

Validation happens before approval and does not write `memory/projects.json`.
The preview shows:

- Projects to create.
- Projects to replace.
- Projects to skip.
- Warnings.
- Validation errors.

Validation collects all detected errors before returning. It checks malformed
JSON, duplicate imported IDs, duplicate imported aliases, invalid project IDs,
invalid command blocks, and invalid editable workspace configuration. Unknown
project and workspace fields are preserved.

Conflict resolution is selected for the entire import operation:

- `skip`: skip imported projects that conflict with existing project IDs or
  aliases.
- `replace`: replace existing projects whose IDs conflict with imported
  projects.
- `rename`: generate deterministic imported project IDs such as
  `docs-import`, and rename conflicting aliases with the imported project ID.

Import requires one approval. The approval summary includes project count,
creates, updates, skips, and the selected resolution. Approval performs one
registry persistence write and one `project_import` Activity History entry.
Rejecting the approval leaves the registry unchanged. Imported commands and
workspace settings are stored only as configuration; Void does not execute
imported commands or automatically trust workspace settings.

### Backing Up and Restoring Projects

Project registry backups are human-readable JSON files stored under:

```text
void/backups/projects/
```

Backup filenames use the deterministic timestamp format:

```text
YYYY-MM-DD_HH-MM-SS_registry.json
```

Creating a backup validates the current registry, preserves unknown registry
fields, writes one JSON file, and logs one `project_backup_created` Activity
History entry. Backup creation follows the approval model for writes.

Restore is always preview-first. Validation checks JSON syntax, backup schema,
backup version, duplicate IDs, duplicate aliases, current project validity, and
registry payload validity. Invalid backups can be inspected, but restore does
not create an approval until validation succeeds.

Restoring a backup requires approval. Approval revalidates the same backup
immediately before the write, performs exactly one registry persistence write,
and logs one `project_backup_restored` Activity History entry. Rejecting the
approval leaves `memory/projects.json` unchanged. Deleting a backup also
requires approval, deletes exactly one backup file, and logs one
`project_backup_deleted` Activity History entry.

Example tool commands:

```text
create_project_backup
list_project_backups
validate_project_backup filename=2026-07-23_12-00-00_registry.json
restore_project_backup filename=2026-07-23_12-00-00_registry.json
delete_project_backup filename=2026-07-23_12-00-00_registry.json
```

The registry also exposes API and Tool Registry operations:

- `GET /projects`
- `GET /projects/{project_id}`
- `GET /projects/current/export`
- `GET /projects/{project_id}/export`
- `GET /projects/export/all`
- `POST /projects/import/validate`
- `POST /projects/import`
- `GET /projects/backups`
- `POST /projects/backups`
- `POST /projects/backups/validate`
- `POST /projects/backups/restore`
- `DELETE /projects/backups`
- `POST /projects`
- `PUT /projects/{project_id}`
- `DELETE /projects/{project_id}`
- `POST /projects/{project_id}/duplicate`
- `list_projects`
- `get_project`
- `export_project`
- `export_projects`
- `validate_project_import`
- `import_projects`
- `create_project_backup`
- `list_project_backups`
- `validate_project_backup`
- `restore_project_backup`
- `delete_project_backup`
- `create_project`
- `update_project`
- `delete_project`
- `duplicate_project`

Selecting the current project continues to use the existing
`set_current_project` implementation and approval flow.

### Smart iTerm2 Workspaces

On macOS, `workspace.terminal.app` may be set to `iterm2`, `iterm`, or `iTerm2`
to use Smart iTerm2 Workspaces. Void uses an exact iTerm2 session marker based
on the project id:

```text
void-workspace:<project_id>
```

When `reuse_existing` is enabled, Void looks only for an iTerm2 session whose
name exactly matches that marker. If one exists, Void activates its window, tab,
and session. If no marked session exists, Void creates a new tab or window,
sets the marker as the session name, and runs the configured
`workspace.terminal.command`. Void does not inspect terminal contents, shell
history, process lists, visible text, or partial filesystem paths. It also does
not control Neovim after launching it.

Approval is always required, including when Void only activates an existing
marked iTerm2 workspace. The command always comes from project configuration;
raw terminal commands are not accepted from the router, API, or Web UI.

Example:

```json
{
  "workspace": {
    "terminal": {
      "app": "iterm2",
      "command": "cd {root} && nvim .",
      "reuse_existing": "true",
      "open_mode": "tab",
      "profile": "Default",
      "window_bounds": "100,80,1500,950"
    }
  }
}
```

Defaults are `reuse_existing=true` and `open_mode=tab`. `profile` and
`window_bounds` are optional. `window_bounds` uses `left,top,right,bottom` and
must contain four integers with `left < right` and `top < bottom`.

## Assistant Flows

Void assistant flows are deterministic-first and tools-first. The router maps
supported project and command requests to registered tools, asks for approval
before state-changing actions, and uses the LLM only as a fallback.

## Activity History

Void records a lightweight execution history in `memory/activity_history.json`.
It is for completed actions such as project commands, visible terminal launches,
browser session open/close events, project switches, repository opens, Git
commits, and scheduler executions. Activity metadata is intentionally compact:
project references store only the project id/name plus the fields needed to
present or replay the action, such as command keys, working directories, browser
URLs, modes, session ids, and return codes.

Activity History is not long-term memory, semantic memory, conversation history,
or prompt storage. It does not store chat messages, LLM responses, or reasoning.
The newest entries are shown first in the CLI, API, and Web UI, and only the
newest 200 entries are kept. Clearing activity history requires approval.

Replay is available only for supported deterministic actions that were executed
through registered tools: project commands, visible project commands, project
workspace opens, project repository opens, project repository browser opens, and
project switches. Replay is not a planner and does not replay arbitrary shell
commands, chat messages, or LLM responses. Replay uses the current project
configuration when it runs again; it does not restore old project snapshots from
activity history. Replayed actions always follow the normal approval process
again.

Useful commands:

```text
/activity
/last-activity
/replay
```

Useful API routes:

```text
GET /activity
GET /activity/latest
POST /activity/clear
POST /activity/replay/latest
POST /activity/replay/{activity_id}
```

Supported project flows:

- Show the current project.
- Switch the current project.
- Open the current project workspace.
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
- No terminal output streaming.
- No attach-to-personal-browser support.

## Git Capability

Examples:

CLI:

```text
git status
покажи diff
какой commit написать
сделай commit с сообщением "Release hardening"
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
make verify
make clean
make cli
make api
make web
```

## Development Status

Release version metadata is read from `void/__version__.py`.

## Roadmap

- Release packaging
- Remote access hardening
- Plugin and skill marketplace

See [docs/roadmap.md](docs/roadmap.md) for the concise roadmap.
