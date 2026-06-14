"""JSON-backed task scheduler storage and helpers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from uuid import uuid4

from void.core.safety import PROJECT_ROOT

TASKS_PATH = PROJECT_ROOT / "memory" / "scheduled_tasks.json"
VALID_SCHEDULE_TYPES = {"once", "interval", "daily"}


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def ensure_scheduler_storage() -> None:
    """Create the scheduler JSON file if it does not exist."""
    TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TASKS_PATH.exists():
        TASKS_PATH.write_text("[]\n", encoding="utf-8")


def load_tasks() -> list[dict]:
    ensure_scheduler_storage()
    try:
        payload = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def save_tasks(tasks: list[dict]) -> None:
    ensure_scheduler_storage()
    TASKS_PATH.write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def list_tasks(include_disabled: bool = True) -> list[dict]:
    tasks = load_tasks()
    if include_disabled:
        return tasks
    return [task for task in tasks if task.get("enabled") is True]


def _validate_schedule(schedule_type: str, schedule_value: dict) -> None:
    if schedule_type not in VALID_SCHEDULE_TYPES:
        raise ValueError(f"Invalid schedule_type: {schedule_type}")
    if not isinstance(schedule_value, dict):
        raise ValueError("schedule_value must be an object")
    if schedule_type == "once" and _parse_iso(schedule_value.get("run_at")) is None:
        raise ValueError("once schedule requires a valid run_at ISO datetime")
    if schedule_type == "interval":
        minutes = schedule_value.get("minutes")
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes <= 0:
            raise ValueError("interval schedule requires positive integer minutes")
    if schedule_type == "daily":
        scheduled_time = schedule_value.get("time")
        if not isinstance(scheduled_time, str):
            raise ValueError("daily schedule requires time in HH:MM format")
        try:
            hour_text, minute_text = scheduled_time.split(":", maxsplit=1)
            hour = int(hour_text)
            minute = int(minute_text)
        except (ValueError, TypeError) as error:
            raise ValueError("daily schedule requires time in HH:MM format") from error
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("daily schedule time is out of range")


def calculate_next_run(schedule_type: str, schedule_value: dict) -> str | None:
    _validate_schedule(schedule_type, schedule_value)
    now = _now()

    if schedule_type == "once":
        run_at = _parse_iso(schedule_value.get("run_at"))
        return _iso(run_at) if run_at is not None else None

    if schedule_type == "interval":
        minutes = schedule_value.get("minutes")
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes <= 0:
            return None
        return _iso(now + timedelta(minutes=minutes))

    scheduled_time = schedule_value.get("time")
    if not isinstance(scheduled_time, str):
        return None
    try:
        hour_text, minute_text = scheduled_time.split(":", maxsplit=1)
        hour = int(hour_text)
        minute = int(minute_text)
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except (ValueError, TypeError):
        return None

    if candidate <= now:
        candidate += timedelta(days=1)
    return _iso(candidate)


def create_task(
    title: str,
    prompt: str,
    schedule_type: str,
    schedule_value: dict,
    enabled: bool = True,
) -> dict:
    _validate_schedule(schedule_type, schedule_value)
    if not title.strip():
        raise ValueError("title is required")
    if not prompt.strip():
        raise ValueError("prompt is required")

    timestamp = _iso(_now())
    task = {
        "id": uuid4().hex[:8],
        "title": title.strip(),
        "prompt": prompt.strip(),
        "schedule_type": schedule_type,
        "schedule_value": schedule_value,
        "enabled": bool(enabled),
        "created_at": timestamp,
        "updated_at": timestamp,
        "last_run_at": None,
        "next_run_at": calculate_next_run(schedule_type, schedule_value),
    }
    tasks = load_tasks()
    tasks.append(task)
    save_tasks(tasks)
    return task


def get_task(task_id: str) -> dict | None:
    for task in load_tasks():
        if task.get("id") == task_id:
            return task
    return None


def update_task(task_id: str, updates: dict) -> dict | None:
    tasks = load_tasks()
    for index, task in enumerate(tasks):
        if task.get("id") != task_id:
            continue

        updated = {**task, **updates}
        schedule_type = updated.get("schedule_type")
        schedule_value = updated.get("schedule_value")
        if not isinstance(schedule_type, str) or not isinstance(schedule_value, dict):
            raise ValueError("Task schedule is invalid")
        _validate_schedule(schedule_type, schedule_value)
        updated["updated_at"] = _iso(_now())
        if (
            "next_run_at" not in updates
            and ("schedule_type" in updates or "schedule_value" in updates)
        ):
            updated["next_run_at"] = calculate_next_run(schedule_type, schedule_value)
        tasks[index] = updated
        save_tasks(tasks)
        return updated

    return None


def delete_task(task_id: str) -> bool:
    tasks = load_tasks()
    remaining = [task for task in tasks if task.get("id") != task_id]
    if len(remaining) == len(tasks):
        return False
    save_tasks(remaining)
    return True


def enable_task(task_id: str) -> dict | None:
    task = get_task(task_id)
    if task is None:
        return None
    next_run_at = calculate_next_run(task["schedule_type"], task["schedule_value"])
    return update_task(task_id, {"enabled": True, "next_run_at": next_run_at})


def disable_task(task_id: str) -> dict | None:
    return update_task(task_id, {"enabled": False})


def due_tasks(now: datetime | None = None) -> list[dict]:
    current = (now or _now()).replace(microsecond=0)
    due: list[dict] = []
    for task in list_tasks(include_disabled=False):
        next_run = _parse_iso(task.get("next_run_at"))
        if next_run is not None and next_run <= current:
            due.append(task)
    return due


def mark_task_ran(task_id: str) -> dict | None:
    task = get_task(task_id)
    if task is None:
        return None

    now_text = _iso(_now())
    updates: dict = {"last_run_at": now_text}
    if task.get("schedule_type") == "once":
        updates["enabled"] = False
        updates["next_run_at"] = None
    else:
        updates["next_run_at"] = calculate_next_run(
            task["schedule_type"],
            task["schedule_value"],
        )
    return update_task(task_id, updates)
