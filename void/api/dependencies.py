"""Shared runtime dependencies for the Void HTTP API."""

from functools import lru_cache

from void.core.agent import Agent
from void.core.registry import ToolRegistry
from void.skills import build_skill_registry
from void.skills.registry import SkillRegistry
from void.tools.builtin import build_registry


@lru_cache(maxsize=1)
def get_tool_registry() -> ToolRegistry:
    """Return the same built-in tool registry used by the CLI."""
    return build_registry()


@lru_cache(maxsize=1)
def get_skill_registry() -> SkillRegistry:
    """Return the same deterministic skill registry used by the CLI."""
    return build_skill_registry()


@lru_cache(maxsize=1)
def get_agent() -> Agent:
    """Return a shared Agent configured with the standard Void registries."""
    return Agent(
        registry=get_tool_registry(),
        skill_registry=get_skill_registry(),
    )
