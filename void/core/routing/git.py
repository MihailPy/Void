"""Deterministic Git route matching."""

import re

from void.core.routing import clean
from void.core.types import AgentAction, RouteResult


def match(text: str, lowered: str) -> RouteResult | None:
    dangerous_git_match = re.search(
        r"\bgit\s+(push|pull|reset|checkout|switch|merge|rebase|clean)\b",
        lowered,
    )
    if dangerous_git_match:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "final_answer",
                {"text": "This git command is not supported for safety reasons."},
                "User asks for an unsupported Git command.",
            ),
        )

    commit_match = re.search(
        r"(?:сделай\s+commit\s+с\s+сообщением|закоммить\s+с\s+сообщением)\s+(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if commit_match:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "git_commit",
                {"message": clean(commit_match.group(1))},
                "User asks to create a Git commit with an explicit message.",
            ),
        )

    git_routes = (
        (
            ("staged diff", "покажи staged"),
            "git_diff",
            {"staged": True},
            "User asks for staged Git diff.",
        ),
        (
            ("git status", "покажи git status", "что изменилось", "какие изменения в git"),
            "git_status",
            {},
            "User asks for Git status.",
        ),
        (
            ("git diff", "покажи diff", "покажи изменения"),
            "git_diff",
            {},
            "User asks for Git diff.",
        ),
        (
            ("git log", "последние коммиты", "история коммитов"),
            "git_log",
            {},
            "User asks for recent Git log.",
        ),
        (
            ("текущая ветка", "какая git ветка", "git branch"),
            "git_current_branch",
            {},
            "User asks for the current Git branch.",
        ),
        (
            ("какой commit написать", "предложи commit message", "сообщение коммита"),
            "git_suggest_commit_message",
            {},
            "User asks for a suggested commit message.",
        ),
    )
    for phrases, action, arguments, reason in git_routes:
        if any(phrase in lowered for phrase in phrases):
            return RouteResult(
                matched=True,
                confidence=0.9,
                action=AgentAction(action, arguments, reason),
            )

    return None
