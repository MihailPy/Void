"""Shared typed contracts for the Void runtime."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    ok: bool
    content: str
    data: dict[str, Any] | None = None
    terminal: bool = False


@dataclass
class ToolDefinition:
    name: str
    description: str
    function: Callable[..., ToolResult]
    terminal: bool = False
    requires_confirmation: bool = False
    category: str = "unknown"
    risk_level: str = "unknown"
    confirmation_validator: Callable[..., Any] | None = None


@dataclass
class AgentAction:
    action: str
    arguments: dict[str, Any]
    reason: str


@dataclass
class ClarificationRequest:
    question: str
    clarification_type: str
    context: dict[str, Any]
    id: str | None = None


@dataclass
class RouteResult:
    matched: bool
    confidence: float
    action: AgentAction | None = None
    clarification: ClarificationRequest | None = None


@dataclass
class AgentResult:
    kind: str
    content: str
    action: AgentAction | None = None
    tool_result: ToolResult | None = None
    clarification: ClarificationRequest | None = None
