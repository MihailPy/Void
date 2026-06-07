"""Typed contracts for deterministic Void skills."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class SkillResult:
    ok: bool
    content: str
    data: dict[str, Any] | None = None
    terminal: bool = True


@dataclass
class SkillDefinition:
    name: str
    description: str
    keywords: list[str]
    function: Callable[..., SkillResult]
    terminal: bool = True


@dataclass
class SkillMatch:
    matched: bool
    confidence: float
    skill: SkillDefinition | None = None
    arguments: dict[str, Any] | None = None
    reason: str = ""
