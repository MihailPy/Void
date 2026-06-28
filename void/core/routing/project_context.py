"""Deterministic project context route matching."""

from __future__ import annotations

import re

from void.core.routing import clean
from void.core.types import AgentAction, RouteResult


def match(text: str, lowered: str) -> RouteResult | None:
    set_match = re.match(
        r"^(?:set\s+current\s+project\s+to|switch\s+project\s+to)\s+(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if set_match is None:
        set_match = re.match(
            r"^(?:переключи\s+проект\s+на|установи\s+текущий\s+проект)\s+(.+)$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    if set_match:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "set_current_project",
                {"project": clean(set_match.group(1))},
                "User asks to change the current project context.",
            ),
        )

    if lowered in {"list projects", "show projects", "покажи проекты", "список проектов"}:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "list_projects",
                {},
                "User asks to list known projects.",
            ),
        )

    if lowered in {
        "current project",
        "what project am i working on",
        "текущий проект",
        "над каким проектом я работаю",
    }:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "get_current_project",
                {},
                "User asks for the current project.",
            ),
        )

    if lowered in {"describe current project", "опиши текущий проект"}:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "describe_current_project",
                {},
                "User asks to describe the current project.",
            ),
        )

    return None
