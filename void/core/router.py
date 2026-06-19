"""Deterministic routing for common Void requests."""

import re
from datetime import datetime, timedelta

from void.core.types import AgentAction, RouteResult


def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def _capability_name(value: str) -> str:
    value = _clean(value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^0-9A-Za-zА-Яа-я_-]+", "", value)
    return value or "requested_capability"


def _task_id(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "", _clean(value))


def _task_title(value: str) -> str:
    cleaned = _clean(value)
    return cleaned[:80] or "Scheduled task"


def _extract_url(value: str) -> str | None:
    match = re.search(r"(https?://[^\s\"'<>]+|[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s\"'<>]*)", value)
    if not match:
        return None
    return _clean(match.group(1)).rstrip(".,;)")


class Router:
    """Simple regex/keyword router that avoids LLM calls for known tasks."""

    def route(self, user_input: str) -> RouteResult:
        text = user_input.strip()
        lowered = text.lower()
        url = _extract_url(text)

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
                    {"message": _clean(commit_match.group(1))},
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

        if url is not None:
            browser_routes = (
                (
                    (
                        "получи текст со страницы",
                        "извлеки текст с сайта",
                        "открой сайт",
                    ),
                    "browser_extract_text",
                    {"url": url},
                    "User asks to extract text from a web page.",
                ),
                (
                    (
                        "сделай скриншот",
                        "скриншот сайта",
                    ),
                    "browser_screenshot",
                    {"url": url},
                    "User asks to take a screenshot of a web page.",
                ),
                (
                    (
                        "покажи ссылки на странице",
                        "собери ссылки с",
                    ),
                    "browser_links",
                    {"url": url},
                    "User asks to collect links from a web page.",
                ),
                (
                    (
                        "какой title у",
                        "заголовок страницы",
                    ),
                    "browser_title",
                    {"url": url},
                    "User asks for the title of a web page.",
                ),
                (
                    (
                        "проверь сайт",
                        "изучи страницу",
                    ),
                    "browser_task",
                    {"url": url, "instruction": text},
                    "User asks for a read-only browser page inspection.",
                ),
            )
            for phrases, action, arguments, reason in browser_routes:
                if any(phrase in lowered for phrase in phrases):
                    return RouteResult(
                        matched=True,
                        confidence=0.9,
                        action=AgentAction(action, arguments, reason),
                    )

        if lowered in {
            "покажи scheduled tasks",
            "покажи запланированные задачи",
            "покажи расписание",
            "scheduled tasks",
            "show scheduled tasks",
        }:
            return RouteResult(
                matched=True,
                confidence=0.95,
                action=AgentAction(
                    "list_scheduled_tasks",
                    {},
                    "User asks to list scheduled tasks.",
                ),
            )

        task_command_match = re.match(
            r"^(?:удали\s+задачу|delete\s+task)\s+([0-9A-Za-z_-]+)$",
            text,
            re.IGNORECASE,
        )
        if task_command_match:
            return RouteResult(
                matched=True,
                confidence=0.95,
                action=AgentAction(
                    "delete_scheduled_task",
                    {"task_id": _task_id(task_command_match.group(1))},
                    "User asks to delete a scheduled task.",
                ),
            )

        task_command_match = re.match(
            r"^(?:отключи\s+задачу|disable\s+task)\s+([0-9A-Za-z_-]+)$",
            text,
            re.IGNORECASE,
        )
        if task_command_match:
            return RouteResult(
                matched=True,
                confidence=0.95,
                action=AgentAction(
                    "disable_scheduled_task",
                    {"task_id": _task_id(task_command_match.group(1))},
                    "User asks to disable a scheduled task.",
                ),
            )

        task_command_match = re.match(
            r"^(?:включи\s+задачу|enable\s+task)\s+([0-9A-Za-z_-]+)$",
            text,
            re.IGNORECASE,
        )
        if task_command_match:
            return RouteResult(
                matched=True,
                confidence=0.95,
                action=AgentAction(
                    "enable_scheduled_task",
                    {"task_id": _task_id(task_command_match.group(1))},
                    "User asks to enable a scheduled task.",
                ),
            )

        task_command_match = re.match(
            r"^(?:запусти\s+задачу|run\s+task)\s+([0-9A-Za-z_-]+)$",
            text,
            re.IGNORECASE,
        )
        if task_command_match:
            return RouteResult(
                matched=True,
                confidence=0.95,
                action=AgentAction(
                    "run_scheduled_task",
                    {"task_id": _task_id(task_command_match.group(1))},
                    "User asks to run a scheduled task.",
                ),
            )

        reminder_match = re.match(
            r"^напомни\s+через\s+(\d+)\s+минут\w*\s+(.+)$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if reminder_match:
            minutes = int(reminder_match.group(1))
            task_text = _clean(reminder_match.group(2))
            run_at = datetime.now().replace(microsecond=0) + timedelta(minutes=minutes)
            return RouteResult(
                matched=True,
                confidence=0.9,
                action=AgentAction(
                    "create_scheduled_task",
                    {
                        "title": _task_title(task_text),
                        "prompt": f"Напомни пользователю: {task_text}",
                        "schedule_type": "once",
                        "schedule_value": {"run_at": run_at.isoformat()},
                    },
                    "User asks to create a one-time reminder.",
                ),
            )

        daily_match = re.match(
            r"^каждый\s+день\s+в\s+([0-2]?\d:[0-5]\d)\s+(.+)$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if daily_match:
            scheduled_time = daily_match.group(1)
            task_text = _clean(daily_match.group(2))
            return RouteResult(
                matched=True,
                confidence=0.9,
                action=AgentAction(
                    "create_scheduled_task",
                    {
                        "title": _task_title(task_text),
                        "prompt": task_text,
                        "schedule_type": "daily",
                        "schedule_value": {"time": scheduled_time},
                    },
                    "User asks to create a daily scheduled task.",
                ),
            )

        interval_match = re.match(
            r"^раз\s+в\s+(\d+)\s+минут\w*\s+(.+)$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if interval_match:
            minutes = int(interval_match.group(1))
            task_text = _clean(interval_match.group(2))
            return RouteResult(
                matched=True,
                confidence=0.9,
                action=AgentAction(
                    "create_scheduled_task",
                    {
                        "title": _task_title(task_text),
                        "prompt": task_text,
                        "schedule_type": "interval",
                        "schedule_value": {"minutes": minutes},
                    },
                    "User asks to create an interval scheduled task.",
                ),
            )

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
                    arguments={"fact": _clean(remember_match.group(1))},
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
                    arguments={"note": _clean(project_note_match.group(1))},
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
                    arguments={"content": _clean(project_update_match.group(1))},
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
                    {"path": _clean(read_match.group(1))},
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
                    {"path": _clean(list_match.group(1))},
                    "User asks to list a directory.",
                ),
            )

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
                    {"name_or_id": _clean(name)},
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
                    {"name_or_id": _clean(name), "reason": _clean(reason)},
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
            name = _capability_name(name)
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

        return RouteResult(matched=False, confidence=0.0)
