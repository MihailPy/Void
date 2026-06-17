from datetime import datetime, timedelta

from void.core import scheduler


def test_create_once_task():
    run_at = (datetime.now() + timedelta(minutes=5)).replace(microsecond=0).isoformat()

    task = scheduler.create_task(
        title="One-time task",
        prompt="Do it",
        schedule_type="once",
        schedule_value={"run_at": run_at},
    )

    assert task["id"]
    assert task["next_run_at"] == run_at
    assert task["enabled"] is True


def test_create_interval_task():
    task = scheduler.create_task(
        title="Interval task",
        prompt="Do it",
        schedule_type="interval",
        schedule_value={"minutes": 10},
    )

    assert task["next_run_at"] is not None


def test_create_daily_task():
    task = scheduler.create_task(
        title="Daily task",
        prompt="Do it",
        schedule_type="daily",
        schedule_value={"time": "09:30"},
    )

    assert task["next_run_at"] is not None


def test_due_tasks_returns_past_enabled_task():
    run_at = (datetime.now() - timedelta(minutes=1)).replace(microsecond=0).isoformat()
    task = scheduler.create_task(
        title="Past task",
        prompt="Do it",
        schedule_type="once",
        schedule_value={"run_at": run_at},
    )

    due = scheduler.due_tasks()

    assert [item["id"] for item in due] == [task["id"]]


def test_mark_once_task_ran_updates_last_run_and_disables_task():
    run_at = (datetime.now() - timedelta(minutes=1)).replace(microsecond=0).isoformat()
    task = scheduler.create_task(
        title="Past task",
        prompt="Do it",
        schedule_type="once",
        schedule_value={"run_at": run_at},
    )

    updated = scheduler.mark_task_ran(task["id"])

    assert updated is not None
    assert updated["last_run_at"] is not None
    assert updated["enabled"] is False
    assert updated["next_run_at"] is None
