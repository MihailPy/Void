"""Registry construction for built-in tools."""

from void.core.registry import ToolRegistry
from void.core import replay
from void.core.types import ToolDefinition, ToolResult
from void.tools import (
    activity_tools,
    browser_tools,
    capability_tools,
    file_tools,
    git_tools,
    memory_tools,
    project_tools,
    scheduler_tools,
)


def final_answer(text: str) -> ToolResult:
    return ToolResult(ok=True, content=text, terminal=True)


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()

    for module in (
        activity_tools,
        file_tools,
        memory_tools,
        project_tools,
        capability_tools,
        scheduler_tools,
        browser_tools,
        git_tools,
    ):
        for definition in module.definitions():
            registry.register(definition)

    registry.register(
        ToolDefinition(
            "repeat_last_activity",
            "Replay the latest supported deterministic activity.",
            lambda: replay.replay_last_action(registry.execute),
            terminal=True,
            category="activity",
            risk_level="write",
        )
    )
    registry.register(
        ToolDefinition(
            "replay_activity",
            "Replay one supported deterministic activity by id.",
            lambda activity_id: replay.replay_activity(activity_id, registry.execute),
            terminal=True,
            category="activity",
            risk_level="write",
        )
    )

    registry.register(
        ToolDefinition(
            "final_answer",
            "Return a direct answer when no tool is required.",
            final_answer,
            terminal=True,
        )
    )
    return registry
