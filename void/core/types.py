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


@dataclass
class AgentAction:
    action: str
    arguments: dict[str, Any]
    reason: str


@dataclass
class RouteResult:
    matched: bool
    confidence: float
    action: AgentAction | None = None

