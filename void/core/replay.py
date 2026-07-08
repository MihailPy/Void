"""Replay support for deterministic activity history entries."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from void.core import activity_history
from void.core.types import AgentAction, ToolResult

UNSUPPORTED_REPLAY_MESSAGE = "Replay is not supported for this action."
NO_PREVIOUS_ACTION_MESSAGE = "No previous action found."

ReplayExecutor = Callable[[AgentAction], ToolResult]

REPLAYABLE_ACTIONS = {
    "run_project_command",
    "run_project_command_visible",
    "open_project_repo",
    "open_project_repo_in_browser",
    "set_current_project",
}


def replay_last_action(execute: ReplayExecutor) -> ToolResult:
    activity = activity_history.get_last_activity()
    if activity is None:
        return ToolResult(
            ok=True,
            content=NO_PREVIOUS_ACTION_MESSAGE,
            data={"activity": None},
            terminal=True,
        )
    return _replay_activity(activity, execute)


def replay_activity(activity_id: str, execute: ReplayExecutor) -> ToolResult:
    activity = activity_history.get_activity(activity_id)
    if activity is None:
        return ToolResult(
            ok=True,
            content=NO_PREVIOUS_ACTION_MESSAGE,
            data={"activity": None, "activity_id": activity_id},
            terminal=True,
        )
    return _replay_activity(activity, execute)


def is_replayable_activity(activity: dict[str, Any]) -> bool:
    return _action_from_activity(activity) is not None


def _replay_activity(activity: dict[str, Any], execute: ReplayExecutor) -> ToolResult:
    action = _action_from_activity(activity)
    if action is None:
        return ToolResult(
            ok=True,
            content=UNSUPPORTED_REPLAY_MESSAGE,
            data={"activity": activity},
            terminal=True,
        )

    result = execute(action)
    if result.data is None:
        result.data = {}
    result.data.setdefault("replayed_activity_id", activity.get("id"))
    result.data.setdefault("replay_action", action.action)
    return result


def _action_from_activity(activity: dict[str, Any]) -> AgentAction | None:
    metadata = _metadata(activity)
    explicit = _explicit_replay_action(metadata)
    if explicit is not None:
        return explicit

    activity_type = str(activity.get("activity_type") or "").strip()
    if activity_type == "project_command":
        command_key = _text(metadata.get("command_key"))
        if not command_key:
            return None
        timeout_seconds = metadata.get("timeout_seconds", 120)
        return _allowed_action(
            "run_project_command",
            {
                "command_key": command_key,
                "timeout_seconds": _positive_int(timeout_seconds, 120),
            },
        )

    if activity_type == "terminal":
        command_key = _text(metadata.get("command_key"))
        if not command_key:
            return None
        return _allowed_action("run_project_command_visible", {"command_key": command_key})

    if activity_type == "project_switch":
        project = _project_identifier(metadata.get("project")) or _text(metadata.get("project"))
        if not project:
            return None
        return _allowed_action("set_current_project", {"project": project})

    if activity_type == "repo_open":
        project = _project_identifier(metadata.get("project")) or _text(metadata.get("project"))
        if not project:
            return None
        mode = _text(metadata.get("mode"))
        if mode:
            return _allowed_action(
                "open_project_repo_in_browser",
                {"project": project, "mode": mode},
            )
        return _allowed_action("open_project_repo", {"project": project})

    return None


def _explicit_replay_action(metadata: dict[str, Any]) -> AgentAction | None:
    replay = metadata.get("replay")
    if not isinstance(replay, dict):
        return None
    action = _text(replay.get("action"))
    arguments = replay.get("arguments", {})
    if action not in REPLAYABLE_ACTIONS or not isinstance(arguments, dict):
        return None
    return _allowed_action(action, arguments)


def _allowed_action(action: str, arguments: dict[str, Any]) -> AgentAction | None:
    if action not in REPLAYABLE_ACTIONS:
        return None
    return AgentAction(
        action=action,
        arguments=arguments,
        reason="Replay deterministic activity history action.",
    )


def _metadata(activity: dict[str, Any]) -> dict[str, Any]:
    metadata = activity.get("metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def _project_identifier(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return _text(value.get("id")) or _text(value.get("name"))


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
