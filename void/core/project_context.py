"""JSON-backed project context storage."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from void.core import activity_history
from void.__version__ import __version__
from void.core.safety import PROJECT_ROOT

PROJECT_CONTEXT_PATH = PROJECT_ROOT / "memory" / "projects.json"
PROJECT_BACKUP_DIR = PROJECT_ROOT / "void" / "backups" / "projects"
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
PROJECT_BACKUP_VERSION = 1

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


def _now() -> datetime:
    return datetime.now()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


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


def _workspace_validation_errors(workspace: Any, project_id: str) -> list[str]:
    from void.core import workspace_preferences

    if workspace is None:
        return []
    if not isinstance(workspace, dict):
        return [f"{project_id}: Workspace must be an object."]

    errors: list[str] = []
    for section, config in workspace.items():
        if not isinstance(config, dict):
            continue
        clean_section = str(section).strip().casefold().replace("-", "_").replace(" ", "_")
        if clean_section == "finder":
            clean_section = "file_manager"
        for field, value in config.items():
            clean_field = str(field).strip().casefold().replace("-", "_").replace(" ", "_")
            if (
                clean_section not in workspace_preferences.EDITABLE_FIELDS
                or clean_field not in workspace_preferences.EDITABLE_FIELDS[clean_section]
            ):
                continue
            try:
                workspace_preferences.validate_preference(section, field, value)
            except ValueError as error:
                errors.append(f"{project_id}: workspace.{section}.{field}: {error}")
    return errors


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


def _parse_import_source(
    source: Any | None = None,
    *,
    path: str | None = None,
) -> tuple[Any | None, list[str]]:
    errors: list[str] = []
    if path is not None and str(path).strip():
        try:
            source = json.loads(Path(str(path)).read_text(encoding="utf-8"))
        except OSError as error:
            errors.append(f"Import file could not be read: {error}")
            return None, errors
        except json.JSONDecodeError as error:
            errors.append(f"Import file is not valid JSON: {error}")
            return None, errors

    if isinstance(source, str):
        try:
            source = json.loads(source)
        except json.JSONDecodeError as error:
            errors.append(f"Import JSON is invalid: {error}")
            return None, errors
    return source, errors


def _import_projects_from_source(source: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if isinstance(source, dict) and "projects" in source:
        projects = source.get("projects")
    elif isinstance(source, dict):
        projects = [source]
    else:
        projects = source

    if not isinstance(projects, list):
        return [], ["Import payload must be one project object, a projects list, or an object with projects."]

    result: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, item in enumerate(projects, start=1):
        if isinstance(item, dict):
            result.append(deepcopy(item))
        else:
            errors.append(f"Project {index}: Each imported project must be an object.")
    if not result and not errors:
        errors.append("Import payload must contain at least one project.")
    return result, errors


def _existing_alias_index(payload: dict[str, Any]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for project in payload["projects"]:
        project_id = str(project.get("id", ""))
        for alias in project.get("aliases", []):
            normalized = _normalize(str(alias))
            if normalized:
                aliases[normalized] = project_id
    return aliases


def _existing_alias_values(payload: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    aliases: dict[str, dict[str, list[str]]] = {}
    for project in payload["projects"]:
        project_id = str(project.get("id", ""))
        for alias in project.get("aliases", []):
            normalized = _normalize(str(alias))
            if normalized:
                aliases.setdefault(normalized, {}).setdefault(project_id, []).append(str(alias))
    return aliases


def _alias_update(
    updates: list[dict[str, Any]],
    *,
    project_id: str,
    import_project_id: str,
) -> dict[str, Any]:
    for update in updates:
        if (
            _normalize(str(update.get("project_id", ""))) == _normalize(project_id)
            and _normalize(str(update.get("import_project_id", "")))
            == _normalize(import_project_id)
        ):
            return update
    update = {
        "project_id": project_id,
        "remove_aliases": [],
        "import_project_id": import_project_id,
        "assign_aliases": [],
    }
    updates.append(update)
    return update


def _record_alias_update(
    updates: list[dict[str, Any]],
    *,
    project_id: str,
    remove_alias: str,
    import_project_id: str,
    assign_alias: str,
) -> None:
    update = _alias_update(
        updates,
        project_id=project_id,
        import_project_id=import_project_id,
    )
    normalized_remove = _normalize(remove_alias)
    if normalized_remove not in {_normalize(alias) for alias in update["remove_aliases"]}:
        update["remove_aliases"].append(remove_alias)
    normalized_assign = _normalize(assign_alias)
    if normalized_assign not in {_normalize(alias) for alias in update["assign_aliases"]}:
        update["assign_aliases"].append(assign_alias)


def _apply_alias_updates(projects: list[dict[str, Any]], updates: list[dict[str, Any]]) -> None:
    removals_by_project: dict[str, set[str]] = {}
    for update in updates:
        project_id = _normalize(str(update.get("project_id", "")))
        if not project_id:
            continue
        removals_by_project.setdefault(project_id, set()).update(
            _normalize(str(alias)) for alias in update.get("remove_aliases", []) if _normalize(str(alias))
        )

    for project in projects:
        normalized_project_id = _normalize(str(project.get("id", "")))
        removals = removals_by_project.get(normalized_project_id)
        if not removals:
            continue
        aliases = project.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        project["aliases"] = [
            alias
            for alias in aliases
            if _normalize(str(alias)) not in removals
        ]


def _duplicate_alias_errors(payload: dict[str, Any]) -> list[str]:
    seen: dict[str, str] = {}
    errors: list[str] = []
    for project in payload.get("projects", []):
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id", ""))
        for alias in project.get("aliases", []):
            normalized = _normalize(str(alias))
            if not normalized:
                continue
            if normalized in seen and _normalize(seen[normalized]) != _normalize(project_id):
                errors.append(
                    f"Duplicate alias after import: {alias} is used by {seen[normalized]} and {project_id}."
                )
            else:
                seen[normalized] = project_id
    return errors


def _next_import_id(base_id: str, reserved_ids: set[str]) -> str:
    stem = base_id
    suffix = "-import"
    candidate = f"{stem}{suffix}"
    counter = 2
    while _normalize(candidate) in reserved_ids:
        candidate = f"{stem}{suffix}-{counter}"
        counter += 1
    return candidate


def _next_import_alias(
    alias: str,
    resolved_project_id: str,
    reserved_aliases: set[str],
) -> str:
    base = f"{alias}-{resolved_project_id}"
    candidate = base
    counter = 2
    while _normalize(candidate) in reserved_aliases:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def _remove_project_by_id(projects: list[dict[str, Any]], project_id: str) -> None:
    normalized_id = _normalize(project_id)
    projects[:] = [
        project
        for project in projects
        if _normalize(str(project.get("id", ""))) != normalized_id
    ]


def _alias_owner(projects: list[dict[str, Any]], alias: str) -> str | None:
    normalized_alias = _normalize(alias)
    for project in projects:
        project_id = str(project.get("id", ""))
        for candidate in project.get("aliases", []):
            if _normalize(str(candidate)) == normalized_alias:
                return project_id
    return None


def _alias_values_for_owner(
    projects: list[dict[str, Any]],
    *,
    project_id: str,
    alias: str,
) -> list[str]:
    normalized_project_id = _normalize(project_id)
    normalized_alias = _normalize(alias)
    values: list[str] = []
    for project in projects:
        if _normalize(str(project.get("id", ""))) != normalized_project_id:
            continue
        for candidate in project.get("aliases", []):
            if _normalize(str(candidate)) == normalized_alias:
                values.append(str(candidate))
    return values or [alias]


def _reserved_aliases(projects: list[dict[str, Any]]) -> set[str]:
    return {
        _normalize(str(alias))
        for project in projects
        for alias in project.get("aliases", [])
        if _normalize(str(alias))
    }


def _final_payload_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    seen_ids: dict[str, str] = {}
    for project in payload.get("projects", []):
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id", ""))
        normalized_id = _normalize(project_id)
        if not normalized_id:
            continue
        if normalized_id in seen_ids:
            errors.append(
                f"Duplicate project id after import: {project_id} is used more than once."
            )
        else:
            seen_ids[normalized_id] = project_id
    errors.extend(_duplicate_alias_errors(payload))
    try:
        _validate_payload(payload)
    except ValueError as error:
        message = str(error)
        if message not in errors:
            errors.append(message)
    return errors


def _strict_registry_errors(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["Project registry root must be an object."]

    projects = payload.get("projects")
    if not isinstance(projects, list):
        return ["Project registry payload must contain a projects list."]
    if not projects:
        errors.append("Project registry must contain at least one project.")

    seen_ids: dict[str, str] = {}
    seen_aliases: dict[str, str] = {}
    project_ids: set[str] = set()
    for index, item in enumerate(projects, start=1):
        label = f"Project {index}"
        if not isinstance(item, dict):
            errors.append(f"{label}: Each project record must be an object.")
            continue
        raw_id = str(item.get("id", "")).strip()
        label = raw_id or label
        try:
            clean = _project_payload(item)
        except ValueError as error:
            errors.append(f"{label}: {error}")
            continue
        normalized_id = _normalize(clean["id"])
        if normalized_id in seen_ids:
            errors.append(f"Duplicate project id: {clean['id']} is also used by {seen_ids[normalized_id]}.")
        else:
            seen_ids[normalized_id] = clean["id"]
            project_ids.add(normalized_id)
        for alias in clean.get("aliases", []):
            normalized_alias = _normalize(str(alias))
            if not normalized_alias:
                continue
            owner = seen_aliases.get(normalized_alias)
            if owner is not None and _normalize(owner) != normalized_id:
                errors.append(
                    f"Duplicate alias: {alias} is used by {owner} and {clean['id']}."
                )
            else:
                seen_aliases[normalized_alias] = clean["id"]

    current_project = str(payload.get("current_project", "")).strip()
    if not current_project:
        errors.append("Current project is required.")
    elif _normalize(current_project) not in project_ids:
        errors.append(f"Current project is not defined: {current_project}")

    try:
        _validate_payload(payload)
    except ValueError as error:
        message = str(error)
        if message not in errors:
            errors.append(message)
    return errors


def _read_project_context_raw() -> dict[str, Any]:
    ensure_project_context()
    try:
        payload = json.loads(PROJECT_CONTEXT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid project context JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("Project context root must be an object.")
    errors = _strict_registry_errors(payload)
    if errors:
        raise ValueError("\n".join(errors))
    return payload


def _backup_path(filename: str | None = None, path: str | None = None) -> Path:
    if filename is not None and str(filename).strip():
        clean_filename = str(filename).strip()
        candidate = Path(clean_filename)
        if candidate.name != clean_filename:
            raise ValueError("Backup filename must not contain directories.")
        resolved = (PROJECT_BACKUP_DIR / clean_filename).resolve()
    elif path is not None and str(path).strip():
        raw_path = Path(str(path).strip())
        resolved = raw_path.resolve() if raw_path.is_absolute() else (PROJECT_BACKUP_DIR / raw_path).resolve()
    else:
        raise ValueError("Backup filename or path is required.")

    try:
        resolved.relative_to(PROJECT_BACKUP_DIR.resolve())
    except ValueError as error:
        raise ValueError("Backup path must stay inside the project backup directory.") from error
    if resolved.suffix != ".json":
        raise ValueError("Backup file must be a JSON file.")
    return resolved


def _load_backup_payload(filename: str | None = None, path: str | None = None) -> tuple[Path, Any, list[str]]:
    backup_path = _backup_path(filename, path)
    try:
        payload = json.loads(backup_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return backup_path, None, [f"Backup file not found: {backup_path.name}"]
    except OSError as error:
        return backup_path, None, [f"Backup file could not be read: {error}"]
    except json.JSONDecodeError as error:
        return backup_path, None, [f"Backup JSON is invalid: {error}"]
    return backup_path, payload, []


def _backup_registry_payload(backup: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in backup.items()
        if key not in {"version", "created_at", "void_version", "metadata"}
    }


def _validate_backup_payload(payload: Any) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    if not isinstance(payload, dict):
        errors.append("Backup root must be an object.")
        return _backup_preview(None, payload, warnings, errors)

    version = payload.get("version")
    if version != PROJECT_BACKUP_VERSION:
        errors.append(f"Unsupported backup version: {version}")
    created_at = str(payload.get("created_at", "")).strip()
    if not created_at:
        errors.append("Backup created_at is required.")
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("Backup metadata must be an object.")

    registry_payload = _backup_registry_payload(payload)
    errors.extend(_strict_registry_errors(registry_payload))

    metadata_count = metadata.get("project_count") if isinstance(metadata, dict) else None
    project_count = len(registry_payload.get("projects", [])) if isinstance(registry_payload.get("projects"), list) else 0
    if metadata_count is not None and metadata_count != project_count:
        warnings.append(
            f"Backup metadata project_count is {metadata_count}, but projects contains {project_count}."
        )
    return _backup_preview(None, payload, warnings, errors)


def _backup_preview(
    backup_path: Path | None,
    payload: Any,
    warnings: list[str],
    errors: list[str],
) -> dict[str, Any]:
    backup = payload if isinstance(payload, dict) else {}
    registry_payload = _backup_registry_payload(backup) if isinstance(backup, dict) else {}
    projects = registry_payload.get("projects", [])
    if not isinstance(projects, list):
        projects = []
    project_summaries = [
        {
            "id": str(project.get("id", "")),
            "name": str(project.get("name", "") or project.get("id", "")),
        }
        for project in projects
        if isinstance(project, dict)
    ]
    filename = backup_path.name if backup_path is not None else ""
    created_at = str(backup.get("created_at", "")).strip()
    current_project = str(registry_payload.get("current_project", "")).strip()
    preview = {
        "ok": not errors,
        "filename": filename,
        "created_at": created_at,
        "project_count": len(project_summaries),
        "current_project": current_project,
        "projects": project_summaries,
        "warnings": warnings,
        "errors": errors,
    }
    preview["summary"] = _format_backup_preview(preview)
    return preview


def _format_backup_preview(preview: dict[str, Any]) -> str:
    filename = preview.get("filename") or "backup"
    lines = [
        "Project backup preview",
        "",
        f"Backup: {filename}",
        f"Created: {preview.get('created_at') or 'unknown'}",
        f"Projects: {preview.get('project_count', 0)}",
        f"Current project: {preview.get('current_project') or 'unknown'}",
    ]
    projects = preview.get("projects", [])
    if isinstance(projects, list) and projects:
        lines.extend(["", "Projects that will exist:"])
        lines.extend(
            f"- {project.get('name') or project.get('id')} ({project.get('id')})"
            for project in projects
            if isinstance(project, dict)
        )
    if preview.get("warnings"):
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in preview["warnings"])
    if preview.get("errors"):
        lines.extend(["", "Validation errors:"])
        lines.extend(f"- {error}" for error in preview["errors"])
    return "\n".join(lines)


def create_project_backup() -> dict[str, Any]:
    registry_payload = _read_project_context_raw()
    created = _now()
    created_at = created.isoformat(timespec="seconds")
    filename = f"{created.strftime('%Y-%m-%d_%H-%M-%S')}_registry.json"
    backup_path = PROJECT_BACKUP_DIR / filename
    backup_payload = {
        "version": PROJECT_BACKUP_VERSION,
        "created_at": created_at,
        "void_version": __version__,
        **deepcopy(registry_payload),
        "metadata": {
            "project_count": len(registry_payload["projects"]),
        },
    }
    _atomic_write_json(backup_path, backup_payload)
    size = backup_path.stat().st_size
    activity_history.log_activity(
        "project_backup_created",
        "success",
        f"Created project registry backup {filename}",
        {
            "path": str(backup_path),
            "filename": filename,
            "project_count": len(registry_payload["projects"]),
        },
    )
    return {
        "path": str(backup_path),
        "project_count": len(registry_payload["projects"]),
        "created_at": created_at,
        "size": size,
    }


def list_project_backups() -> list[dict[str, Any]]:
    PROJECT_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backups: list[dict[str, Any]] = []
    for backup_path in PROJECT_BACKUP_DIR.glob("*.json"):
        created_at = ""
        project_count: int | None = None
        try:
            payload = json.loads(backup_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            created_at = str(payload.get("created_at", "")).strip()
            metadata = payload.get("metadata", {})
            if isinstance(metadata, dict) and isinstance(metadata.get("project_count"), int):
                project_count = metadata["project_count"]
            elif isinstance(payload.get("projects"), list):
                project_count = len(payload["projects"])
        backups.append(
            {
                "filename": backup_path.name,
                "created_at": created_at,
                "size": backup_path.stat().st_size,
                "project_count": project_count,
            }
        )
    return sorted(
        backups,
        key=lambda item: (
            str(item.get("created_at") or ""),
            str(item.get("filename") or ""),
        ),
        reverse=True,
    )


def validate_project_backup(
    filename: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    backup_path, payload, load_errors = _load_backup_payload(filename, path)
    if load_errors:
        return _backup_preview(backup_path, {}, [], load_errors)
    preview = _validate_backup_payload(payload)
    preview["filename"] = backup_path.name
    preview["summary"] = _format_backup_preview(preview)
    return preview


def restore_project_backup(
    filename: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    preview = validate_project_backup(filename, path)
    if preview["errors"]:
        raise ValueError("\n".join(preview["errors"]))

    backup_path, payload, load_errors = _load_backup_payload(filename, path)
    if load_errors:
        raise ValueError("\n".join(load_errors))
    if not isinstance(payload, dict):
        raise ValueError("Backup root must be an object.")
    restored_payload = _backup_registry_payload(payload)
    final_errors = _strict_registry_errors(restored_payload)
    if final_errors:
        raise ValueError("\n".join(final_errors))

    saved = save_project_context(restored_payload)
    activity_history.log_activity(
        "project_backup_restored",
        "success",
        f"Restored project registry backup {backup_path.name}",
        {
            "filename": backup_path.name,
            "path": str(backup_path),
            "project_count": len(saved["projects"]),
            "current_project": saved["current_project"],
        },
    )
    return {
        "preview": preview,
        "projects": saved["projects"],
        "current_project": saved["current_project"],
    }


def restore_project_backup_validation(
    filename: str | None = None,
    path: str | None = None,
) -> None:
    preview = validate_project_backup(filename, path)
    if preview["errors"]:
        raise ValueError("\n".join(preview["errors"]))


def delete_project_backup(
    filename: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    backup_path = _backup_path(filename, path)
    if not backup_path.exists():
        raise ValueError(f"Backup file not found: {backup_path.name}")
    size = backup_path.stat().st_size
    backup_path.unlink()
    activity_history.log_activity(
        "project_backup_deleted",
        "success",
        f"Deleted project registry backup {backup_path.name}",
        {
            "filename": backup_path.name,
            "path": str(backup_path),
            "size": size,
        },
    )
    return {"filename": backup_path.name, "path": str(backup_path), "size": size}


def delete_project_backup_validation(
    filename: str | None = None,
    path: str | None = None,
) -> None:
    backup_path = _backup_path(filename, path)
    if not backup_path.exists():
        raise ValueError(f"Backup file not found: {backup_path.name}")


def plan_project_import(
    source: Any | None = None,
    *,
    path: str | None = None,
    resolution: str = "skip",
) -> dict[str, Any]:
    clean_resolution = str(resolution or "skip").strip().casefold()
    if clean_resolution not in {"replace", "rename", "skip"}:
        clean_resolution = "skip"

    parsed, errors = _parse_import_source(source, path=path)
    imported_projects, project_errors = _import_projects_from_source(parsed) if parsed is not None else ([], [])
    errors.extend(project_errors)

    payload = load_project_context()
    existing_ids = {_normalize(str(project.get("id", ""))) for project in payload["projects"]}
    reserved_ids = set(existing_ids)
    import_ids: dict[str, str] = {}
    warnings: list[str] = []
    creates: list[dict[str, Any]] = []
    replaces: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = []
    resolved_projects: list[dict[str, Any]] = []
    alias_updates: list[dict[str, Any]] = []
    alias_renames: list[dict[str, Any]] = []
    planned_payload = deepcopy(payload)
    planned_projects = planned_payload["projects"]

    for index, raw_project in enumerate(imported_projects, start=1):
        label = str(raw_project.get("id") or f"project {index}").strip()
        try:
            payload_for_known_fields = deepcopy(raw_project)
            payload_for_known_fields["workspace"] = {}
            clean_known = _project_payload(payload_for_known_fields)
        except ValueError as error:
            errors.append(f"{label}: {error}")
            continue

        project_id = clean_known["id"]
        workspace_errors = _workspace_validation_errors(raw_project.get("workspace", {}), project_id)
        errors.extend(workspace_errors)
        if not workspace_errors:
            try:
                clean_known["workspace"] = _validate_workspace(raw_project.get("workspace", {}))
            except ValueError as error:
                errors.append(f"{project_id}: {error}")

        normalized_id = _normalize(project_id)
        if clean_resolution != "rename" and normalized_id in import_ids:
            errors.append(
                f"{project_id}: Duplicate project id in import; already used by {import_ids[normalized_id]}."
            )
            continue
        import_ids[normalized_id] = project_id

        project_record = deepcopy(raw_project)
        project_record.update(clean_known)
        action = "create"

        if normalized_id in existing_ids:
            if clean_resolution == "replace":
                action = "replace"
                replaces.append(project_record)
                _remove_project_by_id(planned_projects, project_id)
            elif clean_resolution == "rename":
                renamed_id = _next_import_id(project_id, reserved_ids)
                warnings.append(f"Renamed imported project {project_id} to {renamed_id}.")
                project_record["id"] = renamed_id
                action = "create"
                creates.append(project_record)
                reserved_ids.add(_normalize(renamed_id))
            else:
                warnings.append(f"Skipped imported project {project_id}: project id already exists.")
                action = "skip"
                skips.append(project_record)
        elif normalized_id in reserved_ids:
            if clean_resolution == "rename":
                renamed_id = _next_import_id(project_id, reserved_ids)
                warnings.append(f"Renamed imported project {project_id} to {renamed_id}.")
                project_record["id"] = renamed_id
                action = "create"
                creates.append(project_record)
                reserved_ids.add(_normalize(renamed_id))
            else:
                errors.append(f"{project_id}: Duplicate project id after import.")
                continue
        else:
            creates.append(project_record)
            reserved_ids.add(normalized_id)

        if action == "skip":
            continue

        resolved_project_id = str(project_record["id"])
        resolved_aliases: list[str] = []
        project_alias_reserved: set[str] = set()
        conflicting_aliases: list[str] = []
        renamed_aliases: list[str] = []

        for alias in project_record.get("aliases", []):
            normalized_alias = _normalize(str(alias))
            owner_id = _alias_owner(planned_projects, str(alias))
            has_conflict = (
                owner_id is not None
                and _normalize(owner_id) != _normalize(resolved_project_id)
            ) or normalized_alias in project_alias_reserved

            if not has_conflict:
                resolved_aliases.append(alias)
                project_alias_reserved.add(normalized_alias)
                continue

            conflicting_aliases.append(str(alias))
            if clean_resolution == "skip":
                continue
            if clean_resolution == "replace" and owner_id is not None:
                existing_values = _alias_values_for_owner(
                    planned_projects,
                    project_id=owner_id,
                    alias=str(alias),
                )
                for existing_value in existing_values:
                    _record_alias_update(
                        alias_updates,
                        project_id=owner_id,
                        remove_alias=existing_value,
                        import_project_id=resolved_project_id,
                        assign_alias=str(alias).strip(),
                    )
                _apply_alias_updates(planned_projects, alias_updates)
                resolved_aliases.append(alias)
                project_alias_reserved.add(normalized_alias)
                continue

            reserved_aliases = _reserved_aliases(planned_projects) | project_alias_reserved
            renamed_alias = _next_import_alias(str(alias).strip(), resolved_project_id, reserved_aliases)
            alias_renames.append(
                {
                    "project_id": resolved_project_id,
                    "from_alias": str(alias),
                    "to_alias": renamed_alias,
                }
            )
            renamed_aliases.append(f"{alias} -> {renamed_alias}")
            resolved_aliases.append(renamed_alias)
            project_alias_reserved.add(_normalize(renamed_alias))

        if conflicting_aliases and clean_resolution == "skip":
            warnings.append(
                f"Skipped imported project {resolved_project_id}: alias conflict(s): {', '.join(conflicting_aliases)}."
            )
            if project_record not in skips:
                skips.append(project_record)
            creates = [project for project in creates if project is not project_record]
            replaces = [project for project in replaces if project is not project_record]
            continue
        if conflicting_aliases and clean_resolution == "replace":
            warnings.append(
                f"Transferring alias ownership for {resolved_project_id}: {', '.join(conflicting_aliases)}."
            )
        if renamed_aliases:
            warnings.append(
                f"Renamed conflicting alias(es) for {resolved_project_id}: {', '.join(renamed_aliases)}."
            )

        project_record["aliases"] = resolved_aliases
        planned_projects.append(deepcopy(project_record))
        resolved_projects.append(project_record)

    planned_payload["projects"] = planned_projects
    errors.extend(error for error in _final_payload_errors(planned_payload) if error not in errors)

    counts = {
        "projects": len(imported_projects),
        "creates": len(creates),
        "updates": len(replaces),
        "skips": len(skips),
    }
    preview = {
        "ok": not errors,
        "version": 1,
        "resolution": clean_resolution,
        "counts": counts,
        "creates": deepcopy(creates),
        "replaces": deepcopy(replaces),
        "skips": deepcopy(skips),
        "alias_updates": deepcopy(alias_updates),
        "alias_renames": deepcopy(alias_renames),
        "warnings": warnings,
        "errors": errors,
        "projects": deepcopy(resolved_projects),
        "final_payload": deepcopy(planned_payload),
    }
    preview["summary"] = _format_import_preview(preview)
    return preview


def _format_import_preview(preview: dict[str, Any]) -> str:
    counts = preview["counts"]
    lines = [
        "Project import preview",
        "",
        f"Projects: {counts['projects']}",
        f"Creates: {counts['creates']}",
        f"Updates: {counts['updates']}",
        f"Skips: {counts['skips']}",
    ]
    if preview["creates"]:
        lines.extend(["", "Projects to create:"])
        lines.extend(f"- {project['name']} ({project['id']})" for project in preview["creates"])
    if preview["replaces"]:
        lines.extend(["", "Projects to replace:"])
        lines.extend(f"- {project['name']} ({project['id']})" for project in preview["replaces"])
    if preview["skips"]:
        lines.extend(["", "Projects to skip:"])
        lines.extend(f"- {project['name']} ({project['id']})" for project in preview["skips"])
    if preview["alias_updates"]:
        lines.extend(["", "Alias ownership changes:"])
        for update in preview["alias_updates"]:
            for alias in update["remove_aliases"]:
                lines.append(f"- Remove alias \"{alias}\" from {update['project_id']}")
            for alias in update["assign_aliases"]:
                lines.append(f"- Assign alias \"{alias}\" to {update['import_project_id']}")
    if preview.get("alias_renames"):
        lines.extend(["", "Alias renames:"])
        for rename in preview["alias_renames"]:
            lines.append(
                f"- {rename['project_id']}: {rename['from_alias']} -> {rename['to_alias']}"
            )
    if preview["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in preview["warnings"])
    if preview["errors"]:
        lines.extend(["", "Validation errors:"])
        lines.extend(f"- {error}" for error in preview["errors"])
    return "\n".join(lines)


def export_projects(
    project: str | None = None,
    *,
    current: bool = False,
    all_projects: bool = False,
) -> dict[str, Any]:
    payload = load_project_context()
    if all_projects:
        selected = deepcopy(payload["projects"])
        scope = "all"
    elif current:
        selected = [deepcopy(get_current_project())]
        scope = "current"
    else:
        if project is None or not str(project).strip():
            raise ValueError("Project is required unless current or all_projects is true.")
        found = find_project(str(project))
        if found is None:
            raise ValueError(f"Project not found: {project}")
        selected = [deepcopy(found)]
        scope = "project"

    result = {"version": 1, "projects": selected}
    activity_history.log_activity(
        "project_export",
        "success",
        f"Exported {len(selected)} project(s)",
        {
            "scope": scope,
            "project_count": len(selected),
            "projects": [activity_history.compact_project(item) for item in selected],
        },
    )
    return result


def validate_project_import(
    source: Any | None = None,
    *,
    path: str | None = None,
    resolution: str = "skip",
) -> dict[str, Any]:
    return plan_project_import(source, path=path, resolution=resolution)


def import_projects(
    source: Any | None = None,
    *,
    path: str | None = None,
    resolution: str = "skip",
) -> dict[str, Any]:
    preview = plan_project_import(source, path=path, resolution=resolution)
    if preview["errors"]:
        raise ValueError("\n".join(preview["errors"]))

    updated_payload = deepcopy(preview["final_payload"])
    final_errors = _final_payload_errors(updated_payload)
    if final_errors:
        raise ValueError("\n".join(final_errors))
    saved = save_project_context(updated_payload)

    counts = preview["counts"]
    activity_history.log_activity(
        "project_import",
        "success",
        (
            "Imported projects: "
            f"{counts['creates']} create(s), {counts['updates']} update(s), {counts['skips']} skip(s)"
        ),
        {
            "project_count": counts["projects"],
            "creates": counts["creates"],
            "updates": counts["updates"],
            "skips": counts["skips"],
            "resolution": preview["resolution"],
            "alias_updates": [
                {
                    "project_id": update["project_id"],
                    "removed_aliases": update["remove_aliases"],
                    "import_project_id": update["import_project_id"],
                    "assigned_aliases": update["assign_aliases"],
                }
                for update in preview["alias_updates"]
            ],
        },
    )
    return {
        "preview": preview,
        "projects": saved["projects"],
        "current_project": saved["current_project"],
    }


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
    _atomic_write_json(PROJECT_CONTEXT_PATH, clean_payload)
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
