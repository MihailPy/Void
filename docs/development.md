# Development

This guide covers the common local development flow for Void.

## Setup

Clone the repository and enter the project root:

```bash
git clone https://github.com/MihailPy/Void.git
cd Void
```

Create a local environment file:

```bash
cp .env.example .env
```

Adjust `.env` as needed for local auth, scheduler worker settings, and the Web UI API URL.

## Install Python Deps

Use your preferred Python environment. With standard `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

If you use `uv`, install from the project metadata:

```bash
uv sync
```

## Install Web Deps

```bash
make web-install
```

or:

```bash
cd web
npm install
```

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

## Run Web

Start the API first, then run:

```bash
make web
```

or:

```bash
cd web
npm run dev
```

## Run Checks

```bash
make check
```

This runs:

```bash
python -m compileall .
```

Clean local caches with:

```bash
make clean
```

## Add a New Tool

1. Add the tool implementation in `void/tools/`.
2. Return a `ToolResult` from the tool function.
3. Register a `ToolDefinition` in that module.
4. Add the module to `void/tools/builtin.py` if it is a new tool module.
5. Set `requires_confirmation=True` for state-changing or sensitive actions.
6. Update README or docs if the tool changes user-facing behavior.

## Add a New Skill

1. Add the skill implementation in `void/skills/`.
2. Support `match_only=True` so the Skill Registry can score the skill.
3. Return a `SkillResult` when executing the skill.
4. Register the skill in the skill builder in `void/skills/__init__.py`.
5. Add practical examples to docs when the skill introduces a new workflow.

## Add a New Capability

1. Check `memory/capabilities/requested.json` for existing requests.
2. Implement the capability as a safe tool, skill, API endpoint, or UI feature.
3. Add approval requirements for protected actions.
4. Move or mark the capability as installed through the existing capability flow.
5. Document the new behavior and any environment requirements.

## Add a New API Endpoint

1. Add request and response schemas in `void/api/schemas.py` when structured payloads are needed.
2. Add the endpoint in `void/api/server.py`.
3. Use `require_api_token` for protected endpoints.
4. Reuse dependencies from `void/api/dependencies.py`.
5. Return consistent `ok` and error payloads.
6. Update `web/src/api.ts` if the Web UI needs the endpoint.
7. Update docs for new public API behavior.

## Update Docs

Keep these files current when behavior changes:

- `README.md` for user-facing setup and commands.
- `docs/architecture.md` for system design.
- `docs/development.md` for contributor workflows.
- `docs/roadmap.md` for completed and upcoming work.
