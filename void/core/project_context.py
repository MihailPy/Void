"""JSON-backed project context storage."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from void.core import activity_history
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


def _require_project_name(name: Any) -> str:
    clean = str(name or "").strip()
    if not clean:
        raise ValueError("Project name is required.")
    return clean


def _require_root_path(root_path: Any) -> str:
    clean = str(root_path or "").strip()
    if not clean:
        raise ValueError("Root path is required.")
    return clean


def _validate_aliases(aliases: Any) -> list[str]:
    if aliases is None:
        return []
    if not isinstance(aliases, list):
        raise ValueError("Aliases must be a list.")
    clean_aliases = [str(alias).strip() for alias in aliases if str(alias).strip()]
    seen: set[str] = set()
    for alias in clean_aliases:
        normalized = _normalize(alias)
        if normalized in seen:
            raise ValueError(f"Duplicate alias: {alias}")
        seen.add(normalized)
    return clean_aliases


def _validate_commands(commands: Any) -> dict[str, str]:
    if commands is None:
        return {}
    if not isinstance(commands, dict):
        raise ValueError("Commands must be an object.")
    clean_commands: dict[str, str] = {}
    seen: set[str] = set()
    for raw_key, raw_command in commands.items():
        key = str(raw_key).strip()
        if not key:
            raise ValueError("Command keys must not be empty.")
        normalized = _normalize(key)
        if normalized in seen:
            raise ValueError(f"Duplicate command key: {key}")
        seen.add(normalized)
        clean_commands[key] = str(raw_command)
    return clean_commands


def _validate_workspace(workspace: Any) -> dict[str, Any]:
    from void.core import workspace_preferences

    if workspace is None:
        return {}
    if not isinstance(workspace, dict):
        raise ValueError("Workspace must be an object.")
    clean_workspace = deepcopy(workspace)
    for section, config in clean_workspace.items():
        if not isinstance(config, dict):
            continue
        clean_section = str(section).strip().casefold().replace("-", "_").replace(" ", "_")
        if clean_section == "finder":
            clean_section = "file_manager"
        for field, value in list(config.items()):
            clean_field = str(field).strip().casefold().replace("-", "_").replace(" ", "_")
            try:
                normalized = workspace_preferences.validate_preference(section, field, value)
            except ValueError:
                if (
                    clean_section in workspace_preferences.EDITABLE_FIELDS
                    and clean_field in workspace_preferences.EDITABLE_FIELDS[clean_section]
                ):
                    raise
            else:
                if clean_section in workspace_preferences.EDITABLE_FIELDS and clean_field in workspace_preferences.EDITABLE_FIELDS[clean_section]:
                    config[field] = normalized
    return clean_workspace


def _merge_workspace(existing: Any, replacement: dict[str, Any]) -> dict[str, Any]:
    from void.core import workspace_preferences

    merged = deepcopy(existing) if isinstance(existing, dict) else {}
    for section, editable_fields in workspace_preferences.EDITABLE_FIELDS.items():
        section_replacement = replacement.get(section, {})
        if not isinstance(section_replacement, dict):
            section_replacement = {}
        section_config = merged.get(section, {})
        if not isinstance(section_config, dict):
            section_config = {}
        else:
            section_config = deepcopy(section_config)
        for field in editable_fields:
            if field in section_replacement:
                section_config[field] = deepcopy(section_replacement[field])
            else:
                section_config.pop(field, None)
        if section_config:
            merged[section] = section_config
        else:
            merged.pop(section, None)
    for section, config in replacement.items():
        if section not in workspace_preferences.EDITABLE_FIELDS:
            merged[section] = deepcopy(config)
    return merged


def _project_index(payload: dict[str, Any], project_id: str) -> int | None:
    normalized = _normalize(project_id)
    for index, project in enumerate(payload["projects"]):
        if _normalize(str(project.get("id", ""))) == normalized:
            return index
    return None


def _validate_unique_project_id(payload: dict[str, Any], project_id: str, original_id: str | None = None) -> None:
    normalized = _normalize(project_id)
    original_normalized = _normalize(original_id or "")
    for project in payload["projects"]:
        candidate = _normalize(str(project.get("id", "")))
        if candidate == normalized and candidate != original_normalized:
            raise ValueError(f"Duplicate project id: {project_id}")


def _project_payload(
    project: dict[str, Any],
    *,
    require_id: bool = True,
) -> dict[str, Any]:
    if require_id or "id" in project:
        project_id = str(project.get("id", "")).strip()
        if not project_id:
            raise ValueError("Project id is required.")
        _validate_project_id(project_id)
    else:
        project_id = ""

    payload: dict[str, Any] = {}
    if project_id:
        payload["id"] = project_id
    if require_id or "name" in project:
        payload["name"] = _require_project_name(project.get("name"))
    if require_id or "root_path" in project:
        payload["root_path"] = _require_root_path(project.get("root_path"))
    if "repo_url" in project or require_id:
        payload["repo_url"] = str(project.get("repo_url") or "").strip()
    if "aliases" in project or require_id:
        payload["aliases"] = _validate_aliases(project.get("aliases", []))
    if "commands" in project or require_id:
        payload["commands"] = _validate_commands(project.get("commands", {}))
    if "workspace" in project or require_id:
        payload["workspace"] = _validate_workspace(project.get("workspace", {}))
    return payload


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
    clean_workspace: dict[str, Any] = {}
    for target, config in workspace.items():
        target_key = str(target).strip()
        if not target_key:
            continue
        if not isinstance(config, dict):
            clean_workspace[target_key] = deepcopy(config)
            continue
        clean_config = {
            str(key).strip(): deepcopy(value)
            for key, value in config.items()
            if str(key).strip()
        }
        clean_workspace[target_key] = clean_config

    project = deepcopy(raw)
    project["id"] = project_id
    project["name"] = name
    project["aliases"] = clean_aliases
    project["root_path"] = str(raw.get("root_path") or ".")
    project["repo_url"] = str(raw.get("repo_url") or "")
    project["commands"] = clean_commands
    if clean_workspace:
        project["workspace"] = clean_workspace
    else:
        project.pop("workspace", None)
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

    clean_payload = deepcopy(payload)
    clean_payload["current_project"] = current_project
    clean_payload["projects"] = clean_projects
    return clean_payload


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


def get_project(project: str) -> dict[str, Any]:
    selected = find_project(project)
    if selected is None:
        raise ValueError(f"Project not found: {project}")
    return selected


def create_project(project: dict[str, Any], duplicate_source_id: str | None = None) -> dict[str, Any]:
    payload = load_project_context()
    clean_project = _project_payload(project)
    _validate_unique_project_id(payload, clean_project["id"])
    updated_payload = deepcopy(payload)
    updated_payload["projects"].append(clean_project)
    saved = save_project_context(updated_payload)
    saved_project = get_project_from_payload(saved, clean_project["id"])
    activity_type = "project_duplicate" if duplicate_source_id else "project_create"
    summary = (
        f"Duplicated project {duplicate_source_id} to {saved_project['name']}"
        if duplicate_source_id
        else f"Created project {saved_project['name']}"
    )
    metadata = {"project": activity_history.compact_project(saved_project)}
    if duplicate_source_id:
        metadata["source_project_id"] = duplicate_source_id
    activity_history.log_activity(activity_type, "success", summary, metadata)
    return {"project": saved_project}


def create_project_validation(project: dict[str, Any], duplicate_source_id: str | None = None) -> None:
    payload = load_project_context()
    clean_project = _project_payload(project)
    _validate_unique_project_id(payload, clean_project["id"])
    if duplicate_source_id is not None and _project_index(payload, duplicate_source_id) is None:
        raise ValueError(f"Project not found: {duplicate_source_id}")


def update_project(project_id: str, project: dict[str, Any]) -> dict[str, Any]:
    payload = load_project_context()
    index = _project_index(payload, project_id)
    if index is None:
        raise ValueError(f"Project not found: {project_id}")
    clean_changes = _project_payload(project, require_id=False)
    new_id = clean_changes.get("id", project_id)
    _validate_unique_project_id(payload, new_id, project_id)
    updated_payload = deepcopy(payload)
    updated_project = deepcopy(updated_payload["projects"][index])
    if "workspace" in clean_changes:
        clean_changes["workspace"] = _merge_workspace(
            updated_project.get("workspace", {}),
            clean_changes["workspace"],
        )
    updated_project.update(clean_changes)
    updated_payload["projects"][index] = updated_project
    if _normalize(str(updated_payload.get("current_project", ""))) == _normalize(project_id):
        updated_payload["current_project"] = updated_project["id"]
    saved = save_project_context(updated_payload)
    saved_project = get_project_from_payload(saved, updated_project["id"])
    activity_history.log_activity(
        "project_update",
        "success",
        f"Updated project {saved_project['name']}",
        {"project": activity_history.compact_project(saved_project)},
    )
    return {"project": saved_project}


def update_project_validation(project_id: str, project: dict[str, Any]) -> None:
    payload = load_project_context()
    if _project_index(payload, project_id) is None:
        raise ValueError(f"Project not found: {project_id}")
    clean_changes = _project_payload(project, require_id=False)
    _validate_unique_project_id(payload, clean_changes.get("id", project_id), project_id)


def delete_project(project_id: str, confirm_current: bool = False) -> dict[str, Any]:
    payload = load_project_context()
    if len(payload["projects"]) <= 1:
        raise ValueError("Cannot delete the last project.")
    index = _project_index(payload, project_id)
    if index is None:
        raise ValueError(f"Project not found: {project_id}")
    deleted = deepcopy(payload["projects"][index])
    is_current = _normalize(str(payload.get("current_project", ""))) == _normalize(str(deleted["id"]))
    if is_current and not confirm_current:
        raise ValueError("Cannot delete the current project without explicit confirmation.")
    updated_payload = deepcopy(payload)
    updated_payload["projects"].pop(index)
    next_project = updated_payload["projects"][0]
    if is_current:
        updated_payload["current_project"] = next_project["id"]
    saved = save_project_context(updated_payload)
    activity_history.log_activity(
        "project_delete",
        "success",
        f"Deleted project {deleted['name']}",
        {
            "project": activity_history.compact_project(deleted),
            "current_project": saved["current_project"],
        },
    )
    return {"project": deleted, "current_project": saved["current_project"]}


def delete_project_validation(project_id: str, confirm_current: bool = False) -> None:
    payload = load_project_context()
    if len(payload["projects"]) <= 1:
        raise ValueError("Cannot delete the last project.")
    index = _project_index(payload, project_id)
    if index is None:
        raise ValueError(f"Project not found: {project_id}")
    selected = payload["projects"][index]
    is_current = _normalize(str(payload.get("current_project", ""))) == _normalize(str(selected["id"]))
    if is_current and not confirm_current:
        raise ValueError("Cannot delete the current project without explicit confirmation.")


def duplicate_project(project_id: str) -> dict[str, Any]:
    payload = load_project_context()
    source = None
    for project in payload["projects"]:
        candidates = [project.get("id", ""), project.get("name", ""), *project.get("aliases", [])]
        if any(_normalize(str(candidate)) == _normalize(project_id) for candidate in candidates):
            source = project
            break
    if source is None:
        raise ValueError(f"Project not found: {project_id}")
    base_id = f"{source['id']}-copy"
    copy_id = base_id
    counter = 2
    while _project_index(payload, copy_id) is not None:
        copy_id = f"{base_id}-{counter}"
        counter += 1
    draft = deepcopy(source)
    draft["id"] = copy_id
    draft["name"] = f"{source['name']} Copy"
    return {"project": draft, "source_project_id": source["id"]}


def get_project_from_payload(payload: dict[str, Any], project_id: str) -> dict[str, Any]:
    for project in payload["projects"]:
        if _normalize(str(project.get("id", ""))) == _normalize(project_id):
            return project
    raise ValueError(f"Project not found: {project_id}")


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
