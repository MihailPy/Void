"""Tool for requesting new built-in capabilities."""

from void.core.types import ToolDefinition, ToolResult


def request_capability(
    name: str,
    problem: str,
    why_self_tool_not_enough: str,
    suggested_function_signature: str,
    suggested_behavior: str,
    usage_example: str,
) -> ToolResult:
    content = (
        "Void requests a new built-in capability.\n\n"
        f"Name:\n{name}\n\n"
        f"Problem:\n{problem}\n\n"
        f"Why existing tools are not enough:\n{why_self_tool_not_enough}\n\n"
        f"Suggested function signature:\n{suggested_function_signature}\n\n"
        f"Suggested behavior:\n{suggested_behavior}\n\n"
        f"Usage example:\n{usage_example}"
    )
    return ToolResult(ok=True, content=content, terminal=True)


def definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            "request_capability",
            "Request a new safe built-in capability when current tools are insufficient.",
            request_capability,
            terminal=True,
        )
    ]

