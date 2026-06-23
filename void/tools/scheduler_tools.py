"""Task scheduler tools."""

from __future__ import annotations

from void.core import scheduler
from void.core.types import ToolDefinition, ToolResult


def _task_line(task: dict) -> str:
    status = "enabled" if task.get("enabled") else "disabled"
    next_run = task.get("next_run_at") or "none"
    last_run = task.get("last_run_at") or "never"
    return (
        f"- {task.get('id', '')} [{status}] {task.get('title', '')}\n"
        f"  type: {task.get('schedule_type', '')}\n"
        f"  next_run_at: {next_run}\n"
        f"  last_run_at: {last_run}"
    )


def list_scheduled_tasks() -> ToolResult:
    tasks = scheduler.list_tasks()
    if not tasks:
        return ToolResult(
            ok=True,
            content="No scheduled tasks.",
            data={"tasks": []},
            terminal=True,
        )

    return ToolResult(
        ok=True,
        content="Scheduled tasks:\n" + "\n".join(_task_line(task) for task in tasks),
        data={"tasks": tasks},
        terminal=True,
    )


def create_scheduled_task(
    title: str,
    prompt: str,
    schedule_type: str,
    schedule_value: dict,
) -> ToolResult:
    task = scheduler.create_task(
        title=title,
        prompt=prompt,
        schedule_type=schedule_type,
        schedule_value=schedule_value,
    )
    return ToolResult(
        ok=True,
        content=(
            f"Scheduled task created: {task['id']}\n"
            f"title: {task['title']}\n"
            f"next_run_at: {task.get('next_run_at') or 'none'}"
        ),
        data={"task": task},
        terminal=True,
    )


def delete_scheduled_task(task_id: str) -> ToolResult:
    if scheduler.delete_task(task_id):
        return ToolResult(ok=True, content=f"Scheduled task deleted: {task_id}", terminal=True)
    return ToolResult(ok=False, content=f"Scheduled task not found: {task_id}", terminal=True)


def enable_scheduled_task(task_id: str) -> ToolResult:
    task = scheduler.enable_task(task_id)
    if task is None:
        return ToolResult(ok=False, content=f"Scheduled task not found: {task_id}", terminal=True)
    return ToolResult(
        ok=True,
        content=f"Scheduled task enabled: {task_id}\nnext_run_at: {task.get('next_run_at') or 'none'}",
        data={"task": task},
        terminal=True,
    )


def disable_scheduled_task(task_id: str) -> ToolResult:
    task = scheduler.disable_task(task_id)
    if task is None:
        return ToolResult(ok=False, content=f"Scheduled task not found: {task_id}", terminal=True)
    return ToolResult(
        ok=True,
        content=f"Scheduled task disabled: {task_id}",
        data={"task": task},
        terminal=True,
    )


def run_scheduled_task(task_id: str) -> ToolResult:
    task = scheduler.get_task(task_id)
    if task is None:
        return ToolResult(ok=False, content=f"Scheduled task not found: {task_id}", terminal=True)

    from void.core.agent import create_default_agent

    agent = create_default_agent()
    result = agent.handle(task["prompt"])
    updated_task = scheduler.mark_task_ran(task_id)
    return ToolResult(
        ok=True,
        content=f"Task {task_id} result:\n{result}",
        data={"task": updated_task or task, "result": result},
        terminal=True,
    )


def definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            "list_scheduled_tasks",
            "List scheduled tasks.",
            list_scheduled_tasks,
            terminal=True,
            category="scheduler",
            risk_level="read",
        ),
        ToolDefinition(
            "create_scheduled_task",
            "Create a scheduled task.",
            create_scheduled_task,
            terminal=True,
            requires_confirmation=True,
            category="scheduler",
            risk_level="write",
        ),
        ToolDefinition(
            "delete_scheduled_task",
            "Delete a scheduled task.",
            delete_scheduled_task,
            terminal=True,
            requires_confirmation=True,
            category="scheduler",
            risk_level="write",
        ),
        ToolDefinition(
            "enable_scheduled_task",
            "Enable a scheduled task.",
            enable_scheduled_task,
            terminal=True,
            requires_confirmation=True,
            category="scheduler",
            risk_level="write",
        ),
        ToolDefinition(
            "disable_scheduled_task",
            "Disable a scheduled task.",
            disable_scheduled_task,
            terminal=True,
            requires_confirmation=True,
            category="scheduler",
            risk_level="write",
        ),
        ToolDefinition(
            "run_scheduled_task",
            "Run a scheduled task manually.",
            run_scheduled_task,
            terminal=True,
            requires_confirmation=True,
            category="scheduler",
            risk_level="write",
        ),
    ]
