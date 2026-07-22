"""JSON-backed pending clarification storage and deterministic resume helpers."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from void.core import project_commands
from void.core.safety import PROJECT_ROOT
from void.core.types import AgentAction

CLARIFICATION_PATH = PROJECT_ROOT / "memory" / "pending_clarification.json"
DEFAULT_STATE: dict[str, Any] = {"pending": None}


def ensure_clarification_storage() -> None:
    """Create the pending clarification file if it does not exist."""
    if CLARIFICATION_PATH.exists():
        return
    CLARIFICATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLARIFICATION_PATH.write_text(
        json.dumps(DEFAULT_STATE, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_state() -> dict[str, Any]:
    ensure_clarification_storage()
    try:
        payload = json.loads(CLARIFICATION_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(DEFAULT_STATE)
    if not isinstance(payload, dict):
        return dict(DEFAULT_STATE)
    pending = payload.get("pending")
    if pending is not None and not isinstance(pending, dict):
        pending = None
    return {"pending": pending}


def _save_state(payload: dict[str, Any]) -> None:
    pending = payload.get("pending")
    if pending is not None and not isinstance(pending, dict):
        pending = None
    CLARIFICATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLARIFICATION_PATH.write_text(
        json.dumps({"pending": pending}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_pending_clarification() -> dict[str, Any] | None:
    """Load the active clarification, if any."""
    return _load_state()["pending"]


def save_pending_clarification(payload: dict[str, Any]) -> None:
    """Replace the active clarification with a serializable payload."""
    _save_state({"pending": payload})


def clear_pending_clarification() -> None:
    """Clear any active clarification."""
    _save_state({"pending": None})


def has_pending_clarification() -> bool:
    """Return whether a clarification is waiting for the next user answer."""
    return load_pending_clarification() is not None


def create_clarification(
    question: str,
    clarification_type: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Create a single pending clarification, replacing any previous one."""
    payload = {
        "id": f"clar_{uuid4().hex[:12]}",
        "question": question,
        "type": clarification_type,
        "context": context,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_pending_clarification(payload)
    return payload


def resolve_clarification(answer: str) -> dict[str, Any] | None:
    """Attach the answer to the pending clarification and clear storage."""
    pending = load_pending_clarification()
    if pending is None:
        return None

    resolved = {
        **pending,
        "answer": answer.strip(),
        "resolved_at": datetime.now().isoformat(timespec="seconds"),
    }
    clear_pending_clarification()
    return resolved


def action_from_resolved_clarification(
    resolved: dict[str, Any],
) -> AgentAction | None:
    """Map a resolved v1 clarification to one deterministic resumed action."""
    answer = str(resolved.get("answer", "")).strip()
    if not answer:
        return None

    context = resolved.get("context", {})
    if not isinstance(context, dict):
        return None

    original_action = str(context.get("original_action", ""))
    clarification_type = str(resolved.get("type", ""))

    if (
        clarification_type == "project_selection"
        and original_action == "open_project_repo"
    ):
        return AgentAction(
            "open_project_repo",
            {"project": answer},
            "User answered a project-selection clarification.",
        )

    if (
        clarification_type == "project_selection"
        and original_action == "open_project_repo_in_browser"
    ):
        return AgentAction(
            "open_project_repo_in_browser",
            {"project": answer},
            "User answered a project-selection clarification.",
        )

    if (
        clarification_type == "project_selection"
        and original_action == "set_current_project"
    ):
        return AgentAction(
            "set_current_project",
            {"project": answer},
            "User answered a project-switch clarification.",
        )

    if (
        clarification_type in {"project_selection", "project_registry"}
        and original_action == "delete_project"
    ):
        return AgentAction(
            "delete_project",
            {"project_id": answer},
            f"Delete project:\n\nProject: {answer}",
        )

    if (
        clarification_type in {"project_selection", "project_registry"}
        and original_action == "duplicate_project"
    ):
        return AgentAction(
            "duplicate_project",
            {"project_id": answer},
            "User answered a project-duplicate clarification.",
        )

    if clarification_type == "project_registry" and original_action == "export_project":
        return AgentAction(
            "export_project",
            {"project": answer},
            "User answered a project-export clarification.",
        )

    if clarification_type == "project_registry" and original_action == "validate_project_import":
        return AgentAction(
            "validate_project_import",
            {"source": answer, "resolution": "skip"},
            "User answered a project-import validation clarification.",
        )

    if clarification_type == "project_registry" and original_action == "import_projects":
        return AgentAction(
            "import_projects",
            {"source": answer, "resolution": "skip"},
            "User answered a project-import clarification.",
        )

    if clarification_type == "project_registry" and original_action == "create_project":
        project_id = "".join(
            character.lower() if character.isalnum() else "-"
            for character in answer
        ).strip("-_")
        while "--" in project_id:
            project_id = project_id.replace("--", "-")
        if not project_id:
            return None
        return AgentAction(
            "create_project",
            {
                "project": {
                    "id": project_id,
                    "name": answer,
                    "root_path": ".",
                    "repo_url": "",
                    "aliases": [],
                    "commands": {},
                    "workspace": {},
                }
            },
            f"Create project:\n\nProject: {answer}\nRoot path: .",
        )

    if (
        clarification_type == "command_selection"
        and original_action == "run_project_command"
    ):
        return AgentAction(
            "run_project_command",
            {"command_key": answer},
            "User answered a project-command clarification.",
        )

    if (
        clarification_type == "command_selection"
        and original_action == "run_project_command_visible"
    ):
        return AgentAction(
            "run_project_command_visible",
            {"command_key": answer},
            "User answered a visible project-command clarification.",
        )

    if (
        clarification_type == "workspace_preference_value"
        and original_action == "update_workspace_preferences"
    ):
        section = str(context.get("section", "")).strip()
        field = str(context.get("field", "")).strip()
        if not section or not field:
            return None
        return AgentAction(
            "update_workspace_preferences",
            {
                "changes": [
                    {
                        "section": section,
                        "field": field,
                        "value": answer,
                    }
                ]
            },
            "User answered a workspace preference clarification.",
        )

    return None


def project_command_options() -> list[str]:
    """Return configured command keys for the current project."""
    try:
        payload = project_commands.list_project_commands()
    except ValueError:
        return []
    commands = payload.get("commands", {})
    if not isinstance(commands, dict):
        return []
    return sorted(str(key) for key in commands)
