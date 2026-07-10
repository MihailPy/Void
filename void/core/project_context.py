"""JSON-backed project context storage."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from void.core.safety import PROJECT_ROOT

PROJECT_CONTEXT_PATH = PROJECT_ROOT / "memory" / "projects.json"
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

DEFAULT_PROJECT_CONTEXT: dict[str, Any] = {
    "current_project": "void",
    "projects": [
        {
            "id": "void",
            "name": "Void",
            "aliases": ["void", "MihailPy/Void"],
            "root_path": ".",
            "repo_url": "https://github.com/MihailPy/Void",
            "workspace": {
                "terminal": {
                    "app": "terminal",
                    "command": "cd {root} && nvim .",
                },
                "browser": {
                    "app": "default",
                },
                "file_manager": {
                    "app": "Finder",
                },
            },
            "commands": {
                "verify": "make verify",
                "test": "make verify",
                "build": "cd web && npm run build",
                "dev": "make web",
            },
        }
    ],
}


def _normalize(value: str) -> str:
    return value.casefold().strip()


def _validate_project_id(project_id: str) -> None:
    if not PROJECT_ID_RE.fullmatch(project_id):
        raise ValueError(
            "Project id must start with a letter or number and contain only "
            "letters, numbers, underscores, or hyphens."
        )


def _clean_project(raw: dict[str, Any]) -> dict[str, Any]:
    project_id = str(raw.get("id", "")).strip()
    _validate_project_id(project_id)

    name = str(raw.get("name") or project_id).strip() or project_id
    aliases = raw.get("aliases", [])
    if not isinstance(aliases, list):
        aliases = []
    clean_aliases = [str(alias).strip() for alias in aliases if str(alias).strip()]

    commands = raw.get("commands", {})
    if not isinstance(commands, dict):
        commands = {}
    clean_commands = {
        str(key).strip(): str(value)
        for key, value in commands.items()
        if str(key).strip()
    }
    workspace = raw.get("workspace", {})
    if not isinstance(workspace, dict):
        workspace = {}
    clean_workspace: dict[str, dict[str, str]] = {}
    for target, config in workspace.items():
        target_key = str(target).strip()
        if not target_key or not isinstance(config, dict):
            continue
        clean_config = {
            str(key).strip(): str(value)
            for key, value in config.items()
            if str(key).strip() and str(value).strip()
        }
        if clean_config:
            clean_workspace[target_key] = clean_config

    project = {
        "id": project_id,
        "name": name,
        "aliases": clean_aliases,
        "root_path": str(raw.get("root_path") or "."),
        "repo_url": str(raw.get("repo_url") or ""),
        "commands": clean_commands,
    }
    if clean_workspace:
        project["workspace"] = clean_workspace
    return project


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    projects = payload.get("projects", [])
    if not isinstance(projects, list):
        raise ValueError("Project context payload must contain a projects list.")

    clean_projects = []
    seen_ids: set[str] = set()
    for item in projects:
        if not isinstance(item, dict):
            raise ValueError("Each project record must be an object.")
        project = _clean_project(item)
        normalized_id = _normalize(project["id"])
        if normalized_id in seen_ids:
            raise ValueError(f"Duplicate project id: {project['id']}")
        seen_ids.add(normalized_id)
        clean_projects.append(project)

    if not clean_projects:
        raise ValueError("Project context must contain at least one project.")

    current_project = str(payload.get("current_project") or clean_projects[0]["id"]).strip()
    if not current_project:
        current_project = clean_projects[0]["id"]

    if not any(_normalize(project["id"]) == _normalize(current_project) for project in clean_projects):
        raise ValueError(f"Current project is not defined: {current_project}")

    return {"current_project": current_project, "projects": clean_projects}


def ensure_project_context() -> None:
    """Create the project context file if it does not exist."""
    if PROJECT_CONTEXT_PATH.exists():
        return
    PROJECT_CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_project_context(deepcopy(DEFAULT_PROJECT_CONTEXT))


def load_project_context() -> dict[str, Any]:
    """Load and validate project context JSON."""
    ensure_project_context()
    try:
        payload = json.loads(PROJECT_CONTEXT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid project context JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("Project context root must be an object.")
    return _validate_payload(payload)


def save_project_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and save project context JSON."""
    clean_payload = _validate_payload(payload)
    PROJECT_CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROJECT_CONTEXT_PATH.write_text(
        json.dumps(clean_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return clean_payload


def list_projects() -> list[dict[str, Any]]:
    return load_project_context()["projects"]


def find_project(project_id_or_alias: str) -> dict[str, Any] | None:
    needle = _normalize(project_id_or_alias)
    if not needle:
        return None

    for project in list_projects():
        candidates = [
            project["id"],
            project["name"],
            *project.get("aliases", []),
        ]
        if any(_normalize(candidate) == needle for candidate in candidates):
            return project
    return None


def get_current_project() -> dict[str, Any]:
    payload = load_project_context()
    project = find_project(payload["current_project"])
    if project is None:
        raise ValueError(f"Current project is not defined: {payload['current_project']}")
    return project


def set_current_project(project_id_or_alias: str) -> dict[str, Any]:
    project = find_project(project_id_or_alias)
    if project is None:
        return {
            "ok": False,
            "error": f"Project not found: {project_id_or_alias}",
        }

    payload = load_project_context()
    payload["current_project"] = project["id"]
    save_project_context(payload)
    return {"ok": True, "project": project}


def describe_current_project() -> str:
    project = get_current_project()
    aliases = ", ".join(project.get("aliases", [])) or "none"
    command_keys = ", ".join(sorted(project.get("commands", {}).keys())) or "none"
    workspace_targets = ", ".join(sorted(project.get("workspace", {}).keys())) or "none"
    repo_url = project.get("repo_url") or "none"

    return (
        "Current project\n\n"
        f"Name: {project['name']}\n"
        f"ID: {project['id']}\n"
        f"Root path: {project.get('root_path', '.')}\n"
        f"Repo URL: {repo_url}\n"
        f"Aliases: {aliases}\n"
        f"Command keys: {command_keys}\n"
        f"Workspace targets: {workspace_targets}"
    )
