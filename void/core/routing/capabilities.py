"""Deterministic capability route matching."""

import re

from void.core.routing import capability_name, clean
from void.core.types import AgentAction, RouteResult


def match(text: str, lowered: str) -> RouteResult | None:
    if any(
        phrase in lowered
        for phrase in (
            "какие у тебя возможности",
            "что ты умеешь",
            "покажи capabilities",
            "список возможностей",
            "список capability",
            "список capabilities",
            "какие capability ожидают реализации",
            "какие capabilities ожидают реализации",
            "capabilities",
        )
    ):
        return RouteResult(
            matched=True,
            confidence=0.9,
            action=AgentAction(
                "list_capabilities",
                {},
                "User asks to list capabilities.",
            ),
        )

    installed_match = re.search(
        r"(?:отметь\s+capability\s+(.+?)\s+как\s+установленн\w*|функция\s+(.+?)\s+реализована|capability\s+(.+?)\s+installed)",
        text,
        re.IGNORECASE,
    )
    if installed_match:
        name = next(group for group in installed_match.groups() if group)
        return RouteResult(
            matched=True,
            confidence=0.9,
            action=AgentAction(
                "mark_capability_installed",
                {"name_or_id": clean(name)},
                "User asks to mark a capability as installed.",
            ),
        )

    reject_match = re.search(
        r"(?:отклони\s+capability\s+(.+?)(?:\s+потому\s+что\s+(.+))?$|reject\s+capability\s+(.+?)(?:\s+because\s+(.+))?$)",
        text,
        re.IGNORECASE,
    )
    if reject_match:
        groups = reject_match.groups()
        name = groups[0] or groups[2] or ""
        reason = groups[1] or groups[3] or "Rejected by user request."
        return RouteResult(
            matched=True,
            confidence=0.9,
            action=AgentAction(
                "reject_capability_request",
                {"name_or_id": clean(name), "reason": clean(reason)},
                "User asks to reject a capability request.",
            ),
        )

    request_match = re.search(
        r"(?:запроси\s+capability\s+(.+)$|добавь\s+запрос\s+на\s+возможность\s+(.+)$|отправь\s+запрос\s+на\s+добавление\s+функции\s+(.+)$|request\s+capability\s+(.+)$)",
        text,
        re.IGNORECASE,
    )
    if request_match:
        name = next(group for group in request_match.groups() if group)
        name = capability_name(name)
        return RouteResult(
            matched=True,
            confidence=0.9,
            action=AgentAction(
                "add_capability_request",
                {
                    "name": name,
                    "description": f"Requested capability: {name}",
                    "problem": text,
                    "reason": "Existing safe built-in tools do not provide this capability.",
                },
                "User asks to request a new capability.",
            ),
        )

    return None
