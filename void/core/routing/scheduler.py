"""Deterministic scheduler route matching."""

import re
from datetime import datetime, timedelta

from void.core.routing import clean, task_id, task_title
from void.core.types import AgentAction, RouteResult


def match(text: str, lowered: str) -> RouteResult | None:
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
                {"task_id": task_id(task_command_match.group(1))},
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
                {"task_id": task_id(task_command_match.group(1))},
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
                {"task_id": task_id(task_command_match.group(1))},
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
                {"task_id": task_id(task_command_match.group(1))},
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
        task_text = clean(reminder_match.group(2))
        run_at = datetime.now().replace(microsecond=0) + timedelta(minutes=minutes)
        return RouteResult(
            matched=True,
            confidence=0.9,
            action=AgentAction(
                "create_scheduled_task",
                {
                    "title": task_title(task_text),
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
        task_text = clean(daily_match.group(2))
        return RouteResult(
            matched=True,
            confidence=0.9,
            action=AgentAction(
                "create_scheduled_task",
                {
                    "title": task_title(task_text),
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
        task_text = clean(interval_match.group(2))
        return RouteResult(
            matched=True,
            confidence=0.9,
            action=AgentAction(
                "create_scheduled_task",
                {
                    "title": task_title(task_text),
                    "prompt": task_text,
                    "schedule_type": "interval",
                    "schedule_value": {"minutes": minutes},
                },
                "User asks to create an interval scheduled task.",
            ),
        )

    return None
