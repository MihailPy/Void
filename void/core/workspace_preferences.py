"""Editable project workspace preference helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from void.core import activity_history, project_context

EDITABLE_FIELDS: dict[str, set[str]] = {
    "terminal": {
        "app",
        "command",
        "reuse_existing",
        "open_mode",
        "profile",
        "window_bounds",
    },
    "browser": {"app"},
    "file_manager": {"app"},
}

TERMINAL_APPS = {"terminal", "iterm", "iterm2"}
OPEN_MODES = {"tab", "window"}
TRUE_VALUES = {"true", "yes", "1", "on"}
FALSE_VALUES = {"false", "no", "0", "off"}


def _normalize_section(section: str) -> str:
    clean = str(section).strip().casefold().replace("-", "_").replace(" ", "_")
    if clean == "finder":
        clean = "file_manager"
    if clean not in EDITABLE_FIELDS:
        supported = ", ".join(sorted(EDITABLE_FIELDS))
        raise ValueError(f"Unsupported workspace preferences section: {section}. Supported sections: {supported}.")
    return clean


def _normalize_field(section: str, field: str) -> str:
    clean = str(field).strip().casefold().replace("-", "_").replace(" ", "_")
    if clean not in EDITABLE_FIELDS[section]:
        supported = ", ".join(sorted(EDITABLE_FIELDS[section]))
        raise ValueError(f"Unsupported workspace preference field for {section}: {field}. Supported fields: {supported}.")
    return clean


def _normalize_bool(value: Any) -> str:
    clean = str(value).strip().casefold()
    if clean in TRUE_VALUES:
        return "true"
    if clean in FALSE_VALUES:
        return "false"
    raise ValueError("reuse_existing must be one of: true, false, yes, no, 1, 0, on, off.")


def _validate_window_bounds(value: Any) -> str:
    clean = str(value).strip()
    parts = [part.strip() for part in clean.split(",")]
    if len(parts) != 4:
        raise ValueError("window_bounds must use the format left,top,right,bottom.")
    try:
        left, top, right, bottom = [int(part) for part in parts]
    except ValueError as error:
        raise ValueError("window_bounds must contain four integers: left,top,right,bottom.") from error
    if left >= right:
        raise ValueError("window_bounds must satisfy left < right.")
    if top >= bottom:
        raise ValueError("window_bounds must satisfy top < bottom.")
    return f"{left},{top},{right},{bottom}"


def validate_preference(section: str, field: str, value: Any) -> str:
    """Validate and normalize one editable workspace preference value."""
    clean_section = _normalize_section(section)
    clean_field = _normalize_field(clean_section, field)
    clean_value = str(value).strip()

    if clean_field == "app" and clean_section == "terminal":
        app = clean_value.casefold()
        if app not in TERMINAL_APPS:
            allowed = ", ".join(sorted(TERMINAL_APPS))
            raise ValueError(f"terminal app must be one of: {allowed}.")
        return "iterm2" if app == "iterm2" else app

    if clean_field == "app":
        if not clean_value:
            raise ValueError(f"{clean_section} app must not be empty.")
        return clean_value

    if clean_field == "command":
        if not clean_value:
            raise ValueError("terminal command must not be empty.")
        if "{root}" not in clean_value:
            raise ValueError("terminal command must contain {root}.")
        return clean_value

    if clean_field == "reuse_existing":
        return _normalize_bool(value)

    if clean_field == "open_mode":
        mode = clean_value.casefold()
        if mode not in OPEN_MODES:
            raise ValueError("open_mode must be one of: tab, window.")
        return mode

    if clean_field == "profile":
        if not clean_value:
            raise ValueError("terminal profile must not be empty.")
        return clean_value

    if clean_field == "window_bounds":
        return _validate_window_bounds(value)

    raise ValueError(f"Unsupported workspace preference field: {field}.")


def get_workspace_preferences(project: str | None = None) -> dict[str, Any]:
    """Return editable workspace preferences for a project."""
    selected = (
        project_context.find_project(project)
        if project is not None and str(project).strip()
        else project_context.get_current_project()
    )
    if selected is None:
        raise ValueError(f"Project not found: {project}")
    workspace = selected.get("workspace", {})
    if not isinstance(workspace, dict):
        workspace = {}
    return {
        "project": {
            "id": selected.get("id", ""),
            "name": selected.get("name", selected.get("id", "")),
        },
        "preferences": deepcopy(workspace),
        "editable_fields": {section: sorted(fields) for section, fields in EDITABLE_FIELDS.items()},
    }


def update_workspace_preference(
    project: str | None,
    section: str,
    field: str,
    value: Any,
) -> dict[str, Any]:
    """Update one editable workspace preference and save via Project Context."""
    clean_section = _normalize_section(section)
    clean_field = _normalize_field(clean_section, field)
    clean_value = validate_preference(clean_section, clean_field, value)

    payload = project_context.load_project_context()
    selected = (
        project_context.find_project(project)
        if project is not None and str(project).strip()
        else project_context.get_current_project()
    )
    if selected is None:
        raise ValueError(f"Project not found: {project}")
    selected_id = str(selected.get("id", ""))

    updated_project: dict[str, Any] | None = None
    old_value: Any = None
    for candidate in payload["projects"]:
        if str(candidate.get("id", "")).casefold() != selected_id.casefold():
            continue
        workspace = candidate.get("workspace", {})
        if not isinstance(workspace, dict):
            workspace = {}
        section_config = workspace.get(clean_section, {})
        if not isinstance(section_config, dict):
            section_config = {}
        old_value = section_config.get(clean_field)
        section_config[clean_field] = clean_value
        workspace[clean_section] = section_config
        candidate["workspace"] = workspace
        updated_project = candidate
        break

    if updated_project is None:
        raise ValueError(f"Project not found: {project or selected_id}")

    saved = project_context.save_project_context(payload)
    saved_project = next(
        project for project in saved["projects"] if str(project.get("id", "")).casefold() == selected_id.casefold()
    )

    activity_history.log_activity(
        "workspace_preferences_update",
        "success",
        f"Updated workspace {clean_section}.{clean_field} for {saved_project.get('name', selected_id)}",
        {
            "project": saved_project,
            "section": clean_section,
            "field": clean_field,
            "old_value": old_value,
            "new_value": clean_value,
        },
    )
    return {
        "project": {
            "id": saved_project.get("id", ""),
            "name": saved_project.get("name", saved_project.get("id", "")),
        },
        "section": clean_section,
        "field": clean_field,
        "old_value": old_value,
        "new_value": clean_value,
        "preferences": deepcopy(saved_project.get("workspace", {})),
    }
