"""Deterministic skills for Void."""

from void.skills import find_text, project_report, summarize_file
from void.skills.registry import SkillRegistry


def build_skill_registry() -> SkillRegistry:
    registry = SkillRegistry()
    for module in (summarize_file, find_text, project_report):
        for definition in module.definitions():
            registry.register(definition)
    return registry
