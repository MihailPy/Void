from void.core.permissions import list_approvals
from void.core.types import AgentAction, ToolDefinition, ToolResult


def test_unknown_tool_returns_error(registry):
    result = registry.execute(AgentAction(action="unknown_tool", arguments={}, reason="test"))

    assert result.ok is False
    assert "Unknown tool" in result.content


def test_registered_tool_executes(registry):
    def hello(name: str) -> ToolResult:
        return ToolResult(ok=True, content=f"Hello, {name}")

    registry.register(ToolDefinition("hello", "Say hello.", hello))

    result = registry.execute(
        AgentAction(action="hello", arguments={"name": "Void"}, reason="test")
    )

    assert result.ok is True
    assert result.content == "Hello, Void"


def test_confirmation_tool_creates_approval_without_executing(registry):
    calls = []

    def dangerous() -> ToolResult:
        calls.append("executed")
        return ToolResult(ok=True, content="done")

    registry.register(
        ToolDefinition(
            "dangerous",
            "Dangerous test tool.",
            dangerous,
            terminal=True,
            requires_confirmation=True,
        )
    )

    result = registry.execute(AgentAction(action="dangerous", arguments={}, reason="test"))

    assert calls == []
    assert result.ok is True
    assert result.terminal is True
    assert "approval" in result.content.lower()
    assert "approve" in result.content.lower()
    approvals = list_approvals()
    assert len(approvals) == 1
    assert approvals[0]["action"] == "dangerous"
