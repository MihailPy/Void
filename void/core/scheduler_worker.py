"""Async background worker for due scheduled tasks."""

from __future__ import annotations

import asyncio
import logging

from void.core import activity_history
from void.core import scheduler
from void.tools.memory_tools import append_session

logger = logging.getLogger(__name__)


class SchedulerWorker:
    """Poll due scheduler tasks and run them through the standard agent."""

    def __init__(self, interval_seconds: int = 60) -> None:
        self.interval_seconds = max(1, int(interval_seconds))
        self.running = False
        self.task: asyncio.Task | None = None
        self._run_lock = asyncio.Lock()

    def start(self) -> None:
        if self.task is not None and not self.task.done():
            return

        self.running = True
        self.task = asyncio.create_task(self.run_loop())

    def stop(self) -> None:
        self.running = False
        if self.task is not None and not self.task.done():
            self.task.cancel()

    async def run_loop(self) -> None:
        try:
            while self.running:
                try:
                    await self.run_once()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Scheduler worker run failed.")

                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            logger.info("Scheduler worker stopped.")
        finally:
            self.running = False

    async def run_once(self) -> list[dict]:
        if self._run_lock.locked():
            logger.warning("Scheduler worker run skipped because another run is active.")
            return []

        async with self._run_lock:
            due = scheduler.due_tasks()
            if not due:
                return []

            from void.core.agent import create_default_agent

            agent = create_default_agent()
            results: list[dict] = []
            for task in due:
                task_id = str(task.get("id", ""))
                title = str(task.get("title", "Untitled task"))
                prompt = str(task.get("prompt", ""))
                if not task_id or not prompt or task.get("enabled") is not True:
                    continue

                result: dict = {
                    "task_id": task_id,
                    "title": title,
                    "ok": False,
                    "result": None,
                    "error": None,
                    "task": task,
                }
                try:
                    output = await asyncio.to_thread(agent.handle, prompt)
                    updated_task = scheduler.mark_task_ran(task_id)
                    result.update(
                        {
                            "ok": True,
                            "result": output,
                            "task": updated_task or task,
                        }
                    )
                    activity_history.log_activity(
                        "scheduler_execution",
                        "success",
                        f"Ran scheduled task {title}",
                        {"task_id": task_id, "title": title},
                    )
                    self._append_run_memory(task_id, title, prompt, output, None)
                except Exception as error:
                    logger.exception("Scheduled task failed: %s", task_id)
                    error_text = str(error)
                    updated_task = scheduler.mark_task_ran(task_id)
                    result["error"] = error_text
                    result["task"] = updated_task or task
                    activity_history.log_activity(
                        "scheduler_execution",
                        "failure",
                        f"Scheduled task failed: {title}",
                        {"task_id": task_id, "title": title},
                    )
                    self._append_run_memory(task_id, title, prompt, None, error_text)

                results.append(result)

            return results

    def _append_run_memory(
        self,
        task_id: str,
        title: str,
        prompt: str,
        result: str | None,
        error: str | None,
    ) -> None:
        content = (
            f"Task ID: {task_id}\n"
            f"Title: {title}\n"
            f"Prompt:\n{prompt}\n\n"
        )
        if error is None:
            content += f"Result:\n{result or ''}"
        else:
            content += f"Error:\n{error}"

        try:
            append_session("Scheduled Task Run", content)
        except Exception:
            logger.exception("Failed to append scheduled task run to session memory.")
