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


def _open_project_workspace_action(
    target: str = "terminal",
    project: str | None = None,
    reason: str = "User asks to open a project workspace.",
) -> RouteResult:
    arguments = {"target": target}
    if project:
        arguments["project"] = project
    return RouteResult(
        matched=True,
        confidence=0.95,
        action=AgentAction("open_project_workspace", arguments, reason),
    )


def _workspace_preferences_action() -> RouteResult:
    return RouteResult(
        matched=True,
        confidence=0.95,
        action=AgentAction(
            "get_workspace_preferences",
            {},
            "User asks to show workspace preferences.",
        ),
    )


def _update_workspace_preferences_action(
    section: str,
    field: str,
    value: str,
    reason: str = "User asks to update workspace preferences.",
) -> RouteResult:
    return RouteResult(
        matched=True,
        confidence=0.95,
        action=AgentAction(
            "update_workspace_preferences",
            {
                "changes": [
                    {
                        "section": section,
                        "field": field,
                        "value": value,
                    }
                ]
            },
            reason,
        ),
    )


def _workspace_preference_clarification(section: str, field: str) -> RouteResult:
    return _clarification_route(
        f"What value should I use for workspace {section}.{field}?",
        "workspace_preference_value",
        {
            "original_action": "update_workspace_preferences",
            "missing_field": "value",
            "section": section,
            "field": field,
        },
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


def _project_registry_clarification(action: str, question: str, missing_field: str) -> RouteResult:
    return _clarification_route(
        question,
        "project_registry",
        {
            "original_action": action,
            "missing_field": missing_field,
            "available_projects": _project_options(),
        },
    )


def match(text: str, lowered: str) -> RouteResult | None:
    if lowered in {"export current project", "экспортируй проект"}:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "export_project",
                {"current": True},
                "User asks to export the current project.",
            ),
        )

    if lowered in {"export all projects", "экспортируй все проекты"}:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "export_projects",
                {},
                "User asks to export all projects.",
            ),
        )

    export_project_match = re.match(
        r"^export\s+project\s+(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if export_project_match:
        project = clean(export_project_match.group(1))
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "export_project",
                {"project": project},
                "User asks to export a selected project.",
            ),
        )

    if lowered in {"export project"}:
        return _project_registry_clarification(
            "export_project",
            "Which project do you want to export?",
            "project",
        )

    if lowered in {
        "import project",
        "import projects",
        "импортируй проект",
        "импортируй проекты",
    }:
        return _project_registry_clarification(
            "import_projects",
            "What project import JSON should I use?",
            "source",
        )

    if lowered in {"validate project import", "проверь импорт проектов"}:
        return _project_registry_clarification(
            "validate_project_import",
            "What project import JSON should I validate?",
            "source",
        )

    if lowered in {
        "create project backup",
        "backup projects",
        "backup project registry",
        "create project registry backup",
    }:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "create_project_backup",
                {},
                "User asks to create a project registry backup.",
            ),
        )

    if lowered in {"list project backups", "show project backups", "project backups"}:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "list_project_backups",
                {},
                "User asks to list project registry backups.",
            ),
        )

    backup_action_patterns = [
        (
            r"^validate\s+project\s+backup\s+(.+)$",
            "validate_project_backup",
            "User asks to validate a project registry backup.",
        ),
        (
            r"^restore\s+project\s+backup\s+(.+)$",
            "restore_project_backup",
            "User asks to restore a project registry backup.",
        ),
        (
            r"^delete\s+project\s+backup\s+(.+)$",
            "delete_project_backup",
            "User asks to delete a project registry backup.",
        ),
    ]
    for pattern, action, reason in backup_action_patterns:
        backup_match = re.match(pattern, text, re.IGNORECASE | re.DOTALL)
        if backup_match:
            return RouteResult(
                matched=True,
                confidence=0.95,
                action=AgentAction(
                    action,
                    {"filename": clean(backup_match.group(1))},
                    reason,
                ),
            )

    if lowered in {"validate project backup", "restore project backup", "delete project backup"}:
        action = lowered.split(" ", 1)[0]
        return _project_registry_clarification(
            f"{action}_project_backup",
            "Which backup filename should I use?",
            "filename",
        )

    if lowered in {
        "create project snapshot",
        "create projects snapshot",
        "создай снимок проектов",
        "создай снимок проекта",
    }:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "create_project_snapshot",
                {"reason": "manual"},
                "User asks to create a project registry snapshot.",
            ),
        )

    if lowered in {
        "list project snapshots",
        "show project snapshots",
        "project snapshots",
        "покажи снимки проектов",
        "покажи историю проектов",
    }:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "list_project_snapshots",
                {},
                "User asks to list project registry snapshots.",
            ),
        )

    snapshot_action_patterns = [
        (
            r"^validate\s+snapshot\s+(.+)$",
            "validate_project_snapshot",
            "User asks to validate a project registry snapshot.",
        ),
        (
            r"^compare\s+snapshot\s+(.+?)(?:\s+with\s+current\s+state)?$",
            "diff_project_snapshot",
            "User asks to compare a project registry snapshot with the current state.",
        ),
        (
            r"^restore\s+snapshot\s+(.+)$",
            "restore_project_snapshot",
            "User asks to restore a project registry snapshot.",
        ),
        (
            r"^delete\s+snapshot\s+(.+)$",
            "delete_project_snapshot",
            "User asks to delete a project registry snapshot.",
        ),
        (
            r"^проверь\s+снимок\s+(.+)$",
            "validate_project_snapshot",
            "User asks to validate a project registry snapshot.",
        ),
        (
            r"^сравни\s+снимок\s+(.+?)(?:\s+с\s+текущим\s+состоянием)?$",
            "diff_project_snapshot",
            "User asks to compare a project registry snapshot with the current state.",
        ),
        (
            r"^(?:восстанови|откати\s+проекты\s+к)\s+снимок\s+(.+)$",
            "restore_project_snapshot",
            "User asks to restore a project registry snapshot.",
        ),
        (
            r"^удали\s+снимок\s+(.+)$",
            "delete_project_snapshot",
            "User asks to delete a project registry snapshot.",
        ),
    ]
    for pattern, action, reason in snapshot_action_patterns:
        snapshot_match = re.match(pattern, text, re.IGNORECASE | re.DOTALL)
        if snapshot_match:
            return RouteResult(
                matched=True,
                confidence=0.95,
                action=AgentAction(
                    action,
                    {"id": clean(snapshot_match.group(1))},
                    reason,
                ),
            )

    if lowered in {
        "validate snapshot",
        "compare snapshot",
        "restore snapshot",
        "delete snapshot",
        "проверь снимок",
        "сравни снимок",
        "восстанови снимок",
        "удали снимок",
    }:
        verb = lowered.split(" ", 1)[0]
        action = {
            "validate": "validate_project_snapshot",
            "compare": "diff_project_snapshot",
            "restore": "restore_project_snapshot",
            "delete": "delete_project_snapshot",
            "проверь": "validate_project_snapshot",
            "сравни": "diff_project_snapshot",
            "восстанови": "restore_project_snapshot",
            "удали": "delete_project_snapshot",
        }.get(verb, "validate_project_snapshot")
        return _project_registry_clarification(
            action,
            "Which snapshot id should I use?",
            "id",
        )

    if lowered in {
        "prune project snapshots",
        "clean old project snapshots",
        "очисти старые снимки проектов",
    }:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "prune_project_snapshots",
                {},
                "User asks to prune old project registry snapshots.",
            ),
        )

    create_named_match = re.match(
        r"^(?:create|add|new)\s+project\s+named\s+(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if create_named_match is None:
        create_named_match = re.match(
            r"^(?:создай|добавь)\s+проект\s+(.+)$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    if create_named_match:
        name = clean(create_named_match.group(1))
        project_id = re.sub(r"[^A-Za-z0-9_-]+", "-", name.strip().lower()).strip("-_")
        if not project_id:
            return _project_registry_clarification(
                "create_project",
                "What project id should I use?",
                "project.id",
            )
        return RouteResult(
            matched=True,
            confidence=0.9,
            action=AgentAction(
                "create_project",
                {
                    "project": {
                        "id": project_id,
                        "name": name,
                        "root_path": ".",
                        "repo_url": "",
                        "aliases": [],
                        "commands": {},
                        "workspace": {},
                    }
                },
                f"Create project:\n\nProject: {name}\nRoot path: .",
            ),
        )

    if lowered in {
        "create project",
        "add project",
        "new project",
        "создай проект",
        "добавь проект",
    }:
        return _project_registry_clarification(
            "create_project",
            "What should the new project be named?",
            "project.name",
        )

    delete_match = re.match(
        r"^delete\s+project\s+(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if delete_match is None:
        delete_match = re.match(
            r"^удали\s+проект\s+(.+)$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    if delete_match:
        project = clean(delete_match.group(1))
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "delete_project",
                {"project_id": project},
                f"Delete project:\n\nProject: {project}",
            ),
        )

    if lowered in {"delete project", "удали проект"}:
        return _project_registry_clarification(
            "delete_project",
            "Which project do you want to delete?",
            "project_id",
        )

    duplicate_match = re.match(
        r"^duplicate\s+project\s+(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if duplicate_match is None:
        duplicate_match = re.match(
            r"^дублируй\s+проект\s+(.+)$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    if duplicate_match:
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "duplicate_project",
                {"project_id": clean(duplicate_match.group(1))},
                "User asks to prepare a duplicate project draft.",
            ),
        )

    if lowered in {"duplicate project", "дублируй проект"}:
        return _project_registry_clarification(
            "duplicate_project",
            "Which project do you want to duplicate?",
            "project_id",
        )

    rename_match = re.match(
        r"^rename\s+project\s+(.+?)\s+to\s+(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if rename_match is None:
        rename_match = re.match(
            r"^переименуй\s+проект\s+(.+?)\s+в\s+(.+)$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    if rename_match:
        project = clean(rename_match.group(1))
        name = clean(rename_match.group(2))
        return RouteResult(
            matched=True,
            confidence=0.95,
            action=AgentAction(
                "update_project",
                {"project_id": project, "project": {"name": name}},
                f"Update project:\n\nProject: {name}\nRoot path: ",
            ),
        )

    if lowered in {"rename project", "переименуй проект"}:
        return _project_registry_clarification(
            "update_project",
            "Which project do you want to rename?",
            "project_id",
        )

    if lowered in {
        "show workspace settings",
        "workspace settings",
        "show workspace preferences",
        "workspace preferences",
        "покажи настройки рабочего пространства",
        "настройки workspace",
    }:
        return _workspace_preferences_action()

    missing_workspace_value_patterns = [
        (r"^set\s+workspace\s+terminal\s+to\s*$", "terminal", "app"),
        (r"^set\s+browser\s+to\s*$", "browser", "app"),
        (r"^set\s+workspace\s+profile\s+to\s*$", "terminal", "profile"),
        (r"^используй\s*$", "terminal", "app"),
        (r"^используй\s+профиль\s*$", "terminal", "profile"),
    ]
    for pattern, section, field in missing_workspace_value_patterns:
        if re.match(pattern, text, re.IGNORECASE | re.DOTALL):
            return _workspace_preference_clarification(section, field)

    workspace_preference_patterns = [
        (r"^set\s+workspace\s+terminal\s+to\s+(.+)$", "terminal", "app"),
        (r"^set\s+browser\s+to\s+(.+)$", "browser", "app"),
        (r"^set\s+workspace\s+profile\s+to\s+(.+)$", "terminal", "profile"),
        (r"^используй\s+профиль\s+(.+)$", "terminal", "profile"),
    ]
    for pattern, section, field in workspace_preference_patterns:
        preference_match = re.match(pattern, text, re.IGNORECASE | re.DOTALL)
        if preference_match:
            return _update_workspace_preferences_action(
                section,
                field,
                clean(preference_match.group(1)),
            )

    use_match = re.match(r"^используй\s+(.+)$", text, re.IGNORECASE | re.DOTALL)
    if use_match:
        value = clean(use_match.group(1))
        if value.casefold() in {"terminal", "iterm", "iterm2"}:
            return _update_workspace_preferences_action("terminal", "app", value)
        return _update_workspace_preferences_action("browser", "app", value)

    workspace_aliases = {
        "open workspace": "terminal",
        "open project": "terminal",
        "open project workspace": "terminal",
        "открой проект": "terminal",
        "открой рабочее пространство": "terminal",
    }
    if lowered in workspace_aliases:
        return _open_project_workspace_action(
            workspace_aliases[lowered],
            reason="User asks to open the current project workspace.",
        )

    workspace_target_aliases = {
        "open project in finder": "finder",
        "open project in file manager": "finder",
        "open project in browser": "browser",
        "open current project on github": "github",
        "open current project in finder": "finder",
        "open current project in browser": "browser",
        "открой проект в finder": "finder",
        "открой проект в файловом менеджере": "finder",
        "открой текущий проект на github": "github",
    }
    if lowered in workspace_target_aliases:
        return _open_project_workspace_action(
            workspace_target_aliases[lowered],
            reason="User asks to open a current project workspace target.",
        )

    workspace_patterns = [
        (r"^open\s+(.+?)\s+project\s+workspace$", "terminal"),
        (r"^open\s+(.+?)\s+project\s+in\s+finder$", "finder"),
        (r"^open\s+(.+?)\s+project\s+in\s+file\s+manager$", "finder"),
        (r"^open\s+(.+?)\s+project\s+on\s+github$", "github"),
        (r"^open\s+(.+?)\s+project\s+in\s+browser$", "browser"),
        (r"^open\s+project\s+(.+?)\s+in\s+finder$", "finder"),
        (r"^open\s+project\s+(.+?)\s+on\s+github$", "github"),
        (r"^open\s+project\s+(.+?)\s+in\s+browser$", "browser"),
        (r"^открой\s+проект\s+(.+?)\s+в\s+finder$", "finder"),
        (r"^открой\s+проект\s+(.+?)\s+на\s+github$", "github"),
    ]
    for pattern, target in workspace_patterns:
        workspace_match = re.match(pattern, text, re.IGNORECASE | re.DOTALL)
        if workspace_match:
            return _open_project_workspace_action(
                target,
                clean(workspace_match.group(1)),
                "User asks to open a configured project workspace target.",
            )

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
