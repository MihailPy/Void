"""JSON-backed project context storage."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
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
    clean_resolution = str(resolution or "skip").strip().casefold()
    if clean_resolution not in {"replace", "rename", "skip"}:
        clean_resolution = "skip"

    parsed, errors = _parse_import_source(source, path=path)
    imported_projects, project_errors = _import_projects_from_source(parsed) if parsed is not None else ([], [])
    errors.extend(project_errors)

    payload = load_project_context()
    existing_ids = {_normalize(str(project.get("id", ""))) for project in payload["projects"]}
    existing_aliases = _existing_alias_index(payload)
    existing_alias_values = _existing_alias_values(payload)
    reserved_ids = set(existing_ids)
    import_ids: dict[str, str] = {}
    import_aliases: dict[str, str] = {}
    warnings: list[str] = []
    creates: list[dict[str, Any]] = []
    replaces: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = []
    resolved_projects: list[dict[str, Any]] = []
    alias_updates: list[dict[str, Any]] = []

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
        if normalized_id in import_ids:
            errors.append(
                f"{project_id}: Duplicate project id in import; already used by {import_ids[normalized_id]}."
            )
            continue
        import_ids[normalized_id] = project_id

        for alias in clean_known.get("aliases", []):
            normalized_alias = _normalize(alias)
            if normalized_alias in import_aliases:
                errors.append(
                    f"{project_id}: Duplicate alias in import: {alias} already used by {import_aliases[normalized_alias]}."
                )
            import_aliases[normalized_alias] = project_id

        project_record = deepcopy(raw_project)
        project_record.update(clean_known)
        action = "create"

        if normalized_id in existing_ids:
            if clean_resolution == "replace":
                action = "replace"
                replaces.append(project_record)
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
        else:
            creates.append(project_record)
            reserved_ids.add(normalized_id)

        if action != "skip":
            conflicting_aliases = [
                alias
                for alias in project_record.get("aliases", [])
                if _normalize(alias) in existing_aliases
                and _normalize(str(existing_aliases[_normalize(alias)])) != _normalize(project_id)
            ]
            if conflicting_aliases:
                if clean_resolution == "skip":
                    warnings.append(
                        f"Skipped imported project {project_record['id']}: alias conflict(s): {', '.join(conflicting_aliases)}."
                    )
                    if project_record not in skips:
                        skips.append(project_record)
                    creates = [project for project in creates if project is not project_record]
                    replaces = [project for project in replaces if project is not project_record]
                    action = "skip"
                elif clean_resolution == "replace":
                    for alias in conflicting_aliases:
                        owner_id = existing_aliases[_normalize(alias)]
                        existing_values = existing_alias_values.get(_normalize(alias), {}).get(
                            owner_id,
                            [alias],
                        )
                        for existing_value in existing_values:
                            _record_alias_update(
                                alias_updates,
                                project_id=owner_id,
                                remove_alias=existing_value,
                                import_project_id=str(project_record["id"]),
                                assign_alias=alias,
                            )
                    warnings.append(
                        f"Transferring alias ownership for {project_record['id']}: {', '.join(conflicting_aliases)}."
                    )
                else:
                    renamed_aliases = []
                    aliases = []
                    for alias in project_record.get("aliases", []):
                        if alias in conflicting_aliases:
                            renamed = f"{alias}-{project_record['id']}"
                            renamed_aliases.append(f"{alias} -> {renamed}")
                            aliases.append(renamed)
                        else:
                            aliases.append(alias)
                    project_record["aliases"] = aliases
                    warnings.append(
                        f"Renamed conflicting alias(es) for {project_record['id']}: {', '.join(renamed_aliases)}."
                    )

        if action != "skip":
            resolved_projects.append(project_record)

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
        "creates": creates,
        "replaces": replaces,
        "skips": skips,
        "alias_updates": alias_updates,
        "warnings": warnings,
        "errors": errors,
        "projects": resolved_projects,
    }
    preview["summary"] = _format_import_preview(preview)
    return preview


def import_projects(
    source: Any | None = None,
    *,
    path: str | None = None,
    resolution: str = "skip",
) -> dict[str, Any]:
    preview = validate_project_import(source, path=path, resolution=resolution)
    if preview["errors"]:
        raise ValueError("\n".join(preview["errors"]))

    payload = load_project_context()
    updated_payload = deepcopy(payload)
    projects = updated_payload["projects"]

    replace_ids = {_normalize(str(project.get("id", ""))) for project in preview["replaces"]}
    if replace_ids:
        projects = [
            project
            for project in projects
            if _normalize(str(project.get("id", ""))) not in replace_ids
        ]

    _apply_alias_updates(projects, preview["alias_updates"])
    projects.extend(deepcopy(preview["projects"]))
    updated_payload["projects"] = projects
    final_errors = _duplicate_alias_errors(updated_payload)
    if final_errors:
        raise ValueError("\n".join(final_errors))
    _validate_payload(updated_payload)
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
