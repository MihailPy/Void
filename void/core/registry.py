"""Tool registry and safe dispatch for Void actions."""

from void.core.types import AgentAction, ToolDefinition, ToolResult


class ToolRegistry:
    """Single source of truth for all executable Void tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def execute(self, action: AgentAction) -> ToolResult:
        tool = self.get(action.action)
        if tool is None:
            return ToolResult(ok=False, content=f"Unknown tool: {action.action}")

        try:
            result = tool.function(**action.arguments)
            result.terminal = result.terminal or tool.terminal
            return result
        except TypeError as error:
            return ToolResult(
                ok=False,
                content=f"Invalid arguments for tool {action.action}: {error}",
                terminal=tool.terminal,
            )
        except Exception as error:
            return ToolResult(
                ok=False,
                content=f"Tool {action.action} failed: {error}",
                terminal=tool.terminal,
            )

