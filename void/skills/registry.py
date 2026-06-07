"""Deterministic registry and matcher for Void skills."""

from void.skills.types import SkillDefinition, SkillMatch, SkillResult


class SkillRegistry:
    """Single source of truth for executable deterministic skills."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> SkillDefinition | None:
        return self._skills.get(name)

    def list_skills(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def match(self, user_input: str) -> SkillMatch:
        best = SkillMatch(matched=False, confidence=0.0)
        for skill in self._skills.values():
            probe = skill.function(user_input=user_input, match_only=True)
            data = probe.data or {}
            confidence = data.get("confidence", 0.0)
            if not isinstance(confidence, int | float):
                confidence = 0.0
            if confidence > best.confidence:
                arguments = data.get("arguments")
                if not isinstance(arguments, dict):
                    arguments = {}
                reason = data.get("reason", "")
                best = SkillMatch(
                    matched=confidence > 0.0,
                    confidence=float(confidence),
                    skill=skill,
                    arguments=arguments,
                    reason=str(reason),
                )
        return best

    def execute(self, match: SkillMatch) -> SkillResult:
        if not match.matched or match.skill is None:
            return SkillResult(ok=False, content="No skill matched.")

        try:
            result = match.skill.function(**(match.arguments or {}))
            result.terminal = result.terminal or match.skill.terminal
            return result
        except TypeError as error:
            return SkillResult(
                ok=False,
                content=f"Invalid arguments for skill {match.skill.name}: {error}",
                terminal=match.skill.terminal,
            )
        except Exception as error:
            return SkillResult(
                ok=False,
                content=f"Skill {match.skill.name} failed: {error}",
                terminal=match.skill.terminal,
            )
