"""Deterministic project context route matching."""

from __future__ import annotations

import re

from void.core import project_context
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


def _open_project_repo_browser_action(project: str, reason: str) -> RouteResult:
    return RouteResult(
        matched=True,
        confidence=0.95,
        action=AgentAction(
            "open_project_repo_in_browser",
            {"project": project},
            reason,
        ),
    )


def _current_project_arg() -> str:
    try:
        return str(project_context.get_current_project()["id"])
    except ValueError:
        return "current"


def _project_options() -> list[str]:
    try:
        return sorted(
            str(project["name"])
            for project in project_context.list_projects()
            if str(project.get("name", "")).strip()
        )
    except ValueError:
        return []


def _project_repo_browser_clarification() -> RouteResult:
    options = _project_options()
    return _clarification_route(
        "Which project do you want to open?",
        "project_selection",
        {
            "original_action": "open_project_repo_in_browser",
            "missing_field": "project",
            "available_projects": options,
        },
    )


def match(text: str, lowered: str) -> RouteResult | None:
    current_repo_phrases = {
        "open current project on github",
        "open current project repo",
        "открой текущий проект на github",
        "открой репозиторий текущего проекта",
    }
    if lowered in current_repo_phrases:
        return _open_project_repo_browser_action(
            _current_project_arg(),
            "User asks to open the current project's configured repository.",
        )

    if lowered in {
        "open project on github",
        "open project github",
        "открой проект на github",
        "открой проект github",
    }:
        return _project_repo_browser_clarification()

    project_repo_patterns = [
        r"^open\s+(.+?)\s+project\s+on\s+github$",
        r"^open\s+project\s+(.+?)\s+on\s+github$",
        r"^open\s+(.+?)\s+repo(?:sitory)?$",
        r"^открой\s+проект\s+(.+?)\s+на\s+github$",
        r"^открой\s+(.+?)\s+на\s+github$",
        r"^открой\s+репозиторий\s+(.+?)$",
    ]
    for pattern in project_repo_patterns:
        project_repo_match = re.match(pattern, text, re.IGNORECASE | re.DOTALL)
        if project_repo_match:
            return _open_project_repo_browser_action(
                clean(project_repo_match.group(1)),
                "User asks to open a configured project repository in a browser.",
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

    if lowered in {
        "run command in terminal",
        "run project command in terminal",
        "open terminal and run command",
        "запусти команду в терминале",
        "запусти команду проекта в терминале",
        "открой терминал и запусти команду",
    }:
        options = project_command_options()
        suffix = f" Available: {', '.join(options)}" if options else ""
        return _clarification_route(
            f"Which command do you want to run in terminal?{suffix}",
            "command_selection",
            {
                "original_action": "run_project_command_visible",
                "missing_field": "command_key",
                "available_commands": options,
            },
        )

    visible_command_match = re.match(
        r"^run\s+project\s+command\s+(.+?)\s+in\s+terminal$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if visible_command_match is None:
        visible_command_match = re.match(
            r"^запусти\s+команду\s+проекта\s+(.+?)\s+в\s+терминале$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    if visible_command_match:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "run_project_command_visible",
                {"command_key": clean(visible_command_match.group(1))},
                "User asks to run a predefined current-project command in a visible terminal.",
            ),
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

    visible_command_aliases = {
        "run tests in terminal": "test",
        "run test in terminal": "test",
        "open terminal and run tests": "test",
        "open terminal and run test": "test",
        "run verification in terminal": "verify",
        "run verify in terminal": "verify",
        "run check in terminal": "verify",
        "run build in terminal": "build",
        "run dev in terminal": "dev",
        "запусти тесты в терминале": "test",
        "запусти тест в терминале": "test",
        "запусти проверку в терминале": "verify",
        "открой терминал и запусти тесты": "test",
        "открой терминал и запусти тест": "test",
        "запусти сборку в терминале": "build",
        "запусти dev в терминале": "dev",
    }
    if lowered in visible_command_aliases:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "run_project_command_visible",
                {"command_key": visible_command_aliases[lowered]},
                "User asks to run a mapped predefined current-project command in a visible terminal.",
            ),
        )

    if lowered in {"switch project", "переключи проект"}:
        options = _project_options()
        return _clarification_route(
            "Which project do you want to switch to?",
            "project_selection",
            {
                "original_action": "set_current_project",
                "missing_field": "project",
                "available_projects": options,
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
