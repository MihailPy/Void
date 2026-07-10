"""Project workspace resolution helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from void.core.safety import PROJECT_ROOT, safe_project_path

SUPPORTED_WORKSPACE_TARGETS = {"terminal", "finder", "github", "browser", "editor"}
TARGET_ALIASES = {
    "file_manager": "finder",
    "file-manager": "finder",
    "file manager": "finder",
}


def _normalize_target(target: str | None) -> str:
    clean = (target or "terminal").strip().casefold()
    clean = TARGET_ALIASES.get(clean, clean)
    if clean not in SUPPORTED_WORKSPACE_TARGETS:
        supported = ", ".join(sorted(SUPPORTED_WORKSPACE_TARGETS))
        raise ValueError(f"Unsupported workspace target: {target}. Supported targets: {supported}.")
    return clean


def _project_root(project: dict[str, Any]) -> Path:
    root_path = str(project.get("root_path") or ".")
    root = safe_project_path(root_path)

    try:
        root.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError("Project workspace root is outside the safe workspace root.") from error

    if not root.exists():
        raise ValueError(f"Project root not found: {root_path}")
    if not root.is_dir():
        raise ValueError(f"Project root is not a directory: {root_path}")

    return root


def get_workspace(project: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Return a project's optional workspace configuration."""
    workspace = project.get("workspace", {})
    if not isinstance(workspace, dict):
        return {}

    clean: dict[str, dict[str, str]] = {}
    for target, config in workspace.items():
        target_key = str(target).strip()
        if not target_key or not isinstance(config, dict):
            continue
        clean[target_key] = {
            str(key): str(value)
            for key, value in config.items()
            if str(key).strip() and str(value).strip()
        }
    return clean


def resolve_workspace_target(
    project: dict[str, Any],
    target: str | None = None,
) -> dict[str, Any]:
    """Resolve one deterministic workspace target for a project."""
    clean_target = _normalize_target(target)
    workspace = get_workspace(project)
    root = _project_root(project)

    config_key = "file_manager" if clean_target == "finder" else clean_target
    config = workspace.get(config_key, {})
    if clean_target == "finder" and not config:
        config = workspace.get("finder", {})

    return {
        "target": clean_target,
        "config": config,
        "workspace": workspace,
        "root": str(root),
        "project": project,
    }
