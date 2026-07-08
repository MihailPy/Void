"""Deterministic activity history route matching."""

from void.core.types import AgentAction, RouteResult


def match(text: str, lowered: str) -> RouteResult | None:
    routes = {
        "show recent activity": (
            "list_recent_activity",
            {},
            "User asks to inspect recent execution activity.",
        ),
        "what did i do": (
            "list_recent_activity",
            {},
            "User asks what actions were executed recently.",
        ),
        "last action": (
            "get_last_activity",
            {},
            "User asks for the latest executed action.",
        ),
        "repeat last action": (
            "repeat_last_activity",
            {},
            "User asks to repeat the latest action.",
        ),
        "repeat previous action": (
            "repeat_last_activity",
            {},
            "User asks to repeat the previous action.",
        ),
        "run that again": (
            "repeat_last_activity",
            {},
            "User asks to repeat the latest action.",
        ),
        "do it again": (
            "repeat_last_activity",
            {},
            "User asks to repeat the latest action.",
        ),
        "clear activity history": (
            "clear_activity_history",
            {},
            "User asks to clear execution activity history.",
        ),
        "покажи последние действия": (
            "list_recent_activity",
            {},
            "User asks to inspect recent execution activity.",
        ),
        "что я делал": (
            "list_recent_activity",
            {},
            "User asks what actions were executed recently.",
        ),
        "последнее действие": (
            "get_last_activity",
            {},
            "User asks for the latest executed action.",
        ),
        "повтори последнее действие": (
            "repeat_last_activity",
            {},
            "User asks to repeat the latest action.",
        ),
        "повтори предыдущую команду": (
            "repeat_last_activity",
            {},
            "User asks to repeat the previous command.",
        ),
        "сделай это еще раз": (
            "repeat_last_activity",
            {},
            "User asks to repeat the latest action.",
        ),
        "очистить историю действий": (
            "clear_activity_history",
            {},
            "User asks to clear execution activity history.",
        ),
    }
    route = routes.get(lowered)
    if route is None:
        return None

    action, arguments, reason = route
    return RouteResult(
        matched=True,
        confidence=0.95,
        action=AgentAction(action, arguments, reason),
    )
