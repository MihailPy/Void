"""Deterministic filesystem and project inspection route matching."""

import re

from void.core.routing import clean
from void.core.types import AgentAction, RouteResult


def match(text: str, lowered: str) -> RouteResult | None:
    if any(
        phrase in lowered
        for phrase in (
            "статистика проекта",
            "статистику проекта",
            "сколько файлов",
            "какие файлы в проекте",
            "сделай статистику проекта",
        )
    ):
        return RouteResult(
            matched=True,
            confidence=0.9,
            action=AgentAction(
                "project_stats",
                {"path": "."},
                "User asks for project statistics.",
            ),
        )

    read_match = re.search(
        r"(?:прочитай файл|покажи файл|read file)\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    if read_match:
        return RouteResult(
            matched=True,
            confidence=0.9,
            action=AgentAction(
                "read_file",
                {"path": clean(read_match.group(1))},
                "User asks to read a specific file.",
            ),
        )

    list_match = re.search(
        r"(?:покажи файлы в|список файлов в|list files in)\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    if list_match:
        return RouteResult(
            matched=True,
            confidence=0.85,
            action=AgentAction(
                "list_files",
                {"path": clean(list_match.group(1))},
                "User asks to list a directory.",
            ),
        )

    return None
