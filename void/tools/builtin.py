"""Registry construction for built-in tools."""

from void.core.registry import ToolRegistry
from void.core.types import ToolDefinition, ToolResult
from void.tools import (
    browser_tools,
    capability_tools,
    file_tools,
    memory_tools,
    project_tools,
    scheduler_tools,
)


def final_answer(text: str) -> ToolResult:
    return ToolResult(ok=True, content=text, terminal=True)


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()

    for module in (
        file_tools,
        memory_tools,
        project_tools,
        capability_tools,
        scheduler_tools,
        browser_tools,
    ):
        for definition in module.definitions():
            registry.register(definition)

    registry.register(
        ToolDefinition(
            "final_answer",
            "Return a direct answer when no tool is required.",
            final_answer,
            terminal=True,
        )
    )
    return registry
