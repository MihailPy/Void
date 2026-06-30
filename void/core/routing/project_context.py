"""Deterministic project context route matching."""

from __future__ import annotations

import re

from void.core.clarification import create_clarification, project_command_options
from void.core.routing import clean
from void.core.types import AgentAction, ClarificationRequest, RouteResult


def _clarification_route(
    question: str,
    clarification_type: str,
    context: dict[str, object],
) -> RouteResult:
    payload = create_clarification(question, clarification_type, context)
    return RouteResult(
        matched=True,
        confidence=0.95,
        clarification=ClarificationRequest(
            question=question,
            clarification_type=clarification_type,
            context=context,
            id=str(payload.get("id", "")),
        ),
    )


def match(text: str, lowered: str) -> RouteResult | None:
    project_repo_match = re.match(
        r"^open\s+(.+?)\s+project\s+on\s+github$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if project_repo_match is None:
        project_repo_match = re.match(
            r"^открой\s+проект\s+(.+?)\s+на\s+github$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    if project_repo_match:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "open_project_repo",
                {"project": clean(project_repo_match.group(1))},
                "User asks for a configured project GitHub repository.",
            ),
        )

    if lowered in {
        "open project on github",
        "open project github",
        "открой проект на github",
        "открой проект github",
    }:
        return _clarification_route(
            "Which project do you want to open?",
            "project_selection",
            {
                "original_action": "open_project_repo",
                "missing_field": "project",
            },
        )

    if lowered in {
        "list project commands",
        "show project commands",
        "what commands does this project have",
        "покажи команды проекта",
        "список команд проекта",
        "какие команды есть у проекта",
    }:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "list_project_commands",
                {},
                "User asks to list predefined commands for the current project.",
            ),
        )

    if lowered in {"run project command", "запусти команду проекта"}:
        options = project_command_options()
        suffix = f" Available: {', '.join(options)}" if options else ""
        return _clarification_route(
            f"Which command do you want to run?{suffix}",
            "command_selection",
            {
                "original_action": "run_project_command",
                "missing_field": "command_key",
                "available_commands": options,
            },
        )

    command_match = re.match(
        r"^run\s+project\s+command\s+(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if command_match is None:
        command_match = re.match(
            r"^запусти\s+команду\s+проекта\s+(.+)$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    if command_match:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "run_project_command",
                {"command_key": clean(command_match.group(1))},
                "User asks to run a predefined current-project command.",
            ),
        )

    command_aliases = {
        "run tests": "test",
        "run test": "test",
        "run verification": "verify",
        "run build": "build",
        "run dev": "dev",
        "запусти тесты": "test",
        "запусти проверку": "verify",
        "запусти сборку": "build",
        "запусти dev": "dev",
    }
    if lowered in command_aliases:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "run_project_command",
                {"command_key": command_aliases[lowered]},
                "User asks to run a mapped predefined current-project command.",
            ),
        )

    if lowered in {"switch project", "переключи проект"}:
        return _clarification_route(
            "Which project do you want to switch to?",
            "project_selection",
            {
                "original_action": "set_current_project",
                "missing_field": "project",
            },
        )

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
