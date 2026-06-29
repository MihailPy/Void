"""Execution helpers for predefined current-project commands."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from void.core.project_context import get_current_project
from void.core.safety import PROJECT_ROOT, safe_project_path


def _project_root(project: dict[str, Any]) -> Path:
    root_path = str(project.get("root_path") or ".")
    root = safe_project_path(root_path)

    try:
        root.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError("Project command cwd is outside the safe workspace root.") from error

    if not root.exists():
        raise ValueError(f"Project root not found: {root_path}")
    if not root.is_dir():
        raise ValueError(f"Project root is not a directory: {root_path}")

    return root


def _commands(project: dict[str, Any]) -> dict[str, str]:
    commands = project.get("commands", {})
    if not isinstance(commands, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in commands.items()
        if str(key).strip() and str(value).strip()
    }


def _text_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def list_project_commands() -> dict[str, Any]:
    """List predefined commands for the current project."""
    project = get_current_project()
    root = _project_root(project)
    commands = dict(sorted(_commands(project).items(), key=lambda item: item[0].casefold()))
    return {
        "project": {
            "id": project["id"],
            "name": project["name"],
        },
        "cwd": str(root),
        "commands": commands,
    }


def get_project_command(command_key: str) -> dict[str, Any]:
    """Resolve a predefined command by key, case-insensitively."""
    needle = command_key.casefold().strip()
    if not needle:
        raise ValueError("Project command key is required.")

    project = get_current_project()
    root = _project_root(project)
    commands = _commands(project)

    for key, command in commands.items():
        if key.casefold() == needle:
            return {
                "key": key,
                "command": command,
                "cwd": str(root),
                "project": {
                    "id": project["id"],
                    "name": project["name"],
                },
            }

    configured = ", ".join(sorted(commands)) or "none"
    raise ValueError(
        f"Project command is not configured: {command_key}. "
        f"Configured command keys: {configured}."
    )


def run_project_command(command_key: str, timeout_seconds: int = 120) -> dict[str, Any]:
    """Run one predefined command for the current project.

    Project commands are configured in memory/projects.json and may contain shell
    syntax such as "cd web && npm run build". For that reason execution uses
    shell=True, but only after resolving a predefined command_key from the
    current project context. User-provided command strings are never executed.
    """
    timeout = int(timeout_seconds)
    if timeout <= 0:
        raise ValueError("timeout_seconds must be greater than 0.")

    resolved = get_project_command(command_key)
    command = resolved["command"]
    cwd = resolved["cwd"]
    started = time.monotonic()

    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            text=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
        duration = time.monotonic() - started
        ok = completed.returncode == 0
        return {
            "ok": ok,
            "timed_out": False,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "returncode": completed.returncode,
            "duration_seconds": round(duration, 3),
            "command": command,
            "command_key": resolved["key"],
            "cwd": cwd,
            "project": resolved["project"],
        }
    except subprocess.TimeoutExpired as error:
        duration = time.monotonic() - started
        stdout = _text_output(error.stdout)
        stderr = _text_output(error.stderr)
        return {
            "ok": False,
            "timed_out": True,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": None,
            "duration_seconds": round(duration, 3),
            "command": command,
            "command_key": resolved["key"],
            "cwd": cwd,
            "project": resolved["project"],
            "error": f"Project command timed out after {timeout} seconds.",
        }
