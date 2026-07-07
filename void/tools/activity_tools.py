"""Tools for inspecting execution activity history."""

from __future__ import annotations

import json

from void.core import activity_history
from void.core.types import ToolDefinition, ToolResult


def _format_activity(activity: dict) -> str:
    return (
        f"- {activity.get('timestamp', '')} "
        f"[{activity.get('status', 'unknown')}] "
        f"{activity.get('activity_type', 'unknown')}: "
        f"{activity.get('summary', '')}"
    )


def list_recent_activity(limit: int = 20) -> ToolResult:
    activities = activity_history.list_recent(limit)
    if not activities:
        return ToolResult(
            ok=True,
            content="No activity history.",
            data={"activities": []},
            terminal=True,
        )
    return ToolResult(
        ok=True,
        content="Recent activity:\n" + "\n".join(_format_activity(item) for item in activities),
        data={"activities": activities},
        terminal=True,
    )


def get_last_activity() -> ToolResult:
    activity = activity_history.get_last_activity()
    if activity is None:
        return ToolResult(
            ok=True,
            content="No activity history.",
            data={"activity": None},
            terminal=True,
        )
    return ToolResult(
        ok=True,
        content="Last activity:\n" + _format_activity(activity),
        data={"activity": activity},
        terminal=True,
    )


def repeat_last_activity() -> ToolResult:
    activity = activity_history.get_last_activity()
    if activity is None:
        return ToolResult(
            ok=True,
            content="Replay is not implemented yet.\nNo last action was found.",
            data={"activity": None},
            terminal=True,
        )
    return ToolResult(
        ok=True,
        content=(
            "Replay is not implemented yet.\n"
            f"Last action was: {_format_activity(activity)}\n"
            "Metadata:\n"
            f"{json.dumps(activity.get('metadata', {}), ensure_ascii=False, indent=2)}"
        ),
        data={"activity": activity},
        terminal=True,
    )


def clear_activity_history() -> ToolResult:
    activity_history.clear_history()
    return ToolResult(
        ok=True,
        content="Activity history cleared.",
        data={"activities": []},
        terminal=True,
    )


def definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            "list_recent_activity",
            "List recent execution activity history.",
            list_recent_activity,
            terminal=True,
            category="activity",
            risk_level="read",
        ),
        ToolDefinition(
            "get_last_activity",
            "Show the latest execution activity.",
            get_last_activity,
            terminal=True,
            category="activity",
            risk_level="read",
        ),
        ToolDefinition(
            "repeat_last_activity",
            "Explain that activity replay is not implemented and show the last action.",
            repeat_last_activity,
            terminal=True,
            category="activity",
            risk_level="read",
        ),
        ToolDefinition(
            "clear_activity_history",
            "Clear execution activity history after approval.",
            clear_activity_history,
            terminal=True,
            requires_confirmation=True,
            category="activity",
            risk_level="write",
        ),
    ]
