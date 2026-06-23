"""Deterministic memory route matching."""

import re

from void.core.routing import clean
from void.core.types import AgentAction, RouteResult


def match(text: str, lowered: str) -> RouteResult | None:
    remember_match = re.match(
        r"^(?:запомни|remember)\s*[:：]\s*(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if remember_match:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                action="remember_fact",
                arguments={"fact": clean(remember_match.group(1))},
                reason="User explicitly asked to remember a fact.",
            ),
        )

    project_note_match = re.match(
        r"^запомни\s+в\s+памяти\s+проекта\s*[:：]\s*(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if project_note_match:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                action="append_project_note",
                arguments={"note": clean(project_note_match.group(1))},
                reason="User explicitly asked to append a project memory note.",
            ),
        )

    project_update_match = re.match(
        r"^полностью\s+перезапиши\s+память\s+проекта\s*[:：]\s*(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if project_update_match:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                action="update_project",
                arguments={"content": clean(project_update_match.group(1))},
                reason="User explicitly asked to update project memory.",
            ),
        )

    if any(phrase in lowered for phrase in ("что ты помнишь", "какие факты", "что запомнено")):
        return RouteResult(
            matched=True,
            confidence=0.9,
            action=AgentAction(
                "read_facts",
                {},
                "User asks to read remembered facts.",
            ),
        )

    if lowered == "память проекта" or any(
        phrase in lowered
        for phrase in (
            "что реализовано",
            "состояние проекта",
            "что дальше",
            "покажи память проекта",
            "прочитай память проекта",
            "что в памяти проекта",
        )
    ):
        return RouteResult(
            matched=True,
            confidence=0.85,
            action=AgentAction("read_project", {}, "User asks for project memory."),
        )

    return None
