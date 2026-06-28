from __future__ import annotations

import pytest


@pytest.fixture
def temp_memory_dir(tmp_path, monkeypatch):
    memory_dir = tmp_path / "memory"
    capabilities_dir = memory_dir / "capabilities"
    capabilities_dir.mkdir(parents=True)

    monkeypatch.setenv("VOID_SCHEDULER_WORKER_ENABLED", "0")
    monkeypatch.delenv("VOID_API_TOKEN", raising=False)

    from void.api import dependencies
    from void.api import server
    from void.core import capabilities, permissions, project_context, safety, scheduler
    from void.tools import memory_tools

    monkeypatch.setattr(safety, "MEMORY_DIR", memory_dir)
    monkeypatch.setattr(memory_tools, "MEMORY_DIR", memory_dir)
    monkeypatch.setattr(server, "MEMORY_DIR", memory_dir)

    monkeypatch.setattr(scheduler, "TASKS_PATH", memory_dir / "scheduled_tasks.json")
    monkeypatch.setattr(permissions, "APPROVALS_PATH", memory_dir / "pending_approvals.json")
    monkeypatch.setattr(project_context, "PROJECT_CONTEXT_PATH", memory_dir / "projects.json")

    monkeypatch.setattr(capabilities, "CAPABILITY_DIR", capabilities_dir)
    monkeypatch.setattr(capabilities, "INSTALLED_PATH", capabilities_dir / "installed.json")
    monkeypatch.setattr(capabilities, "REQUESTED_PATH", capabilities_dir / "requested.json")
    monkeypatch.setattr(capabilities, "REJECTED_PATH", capabilities_dir / "rejected.json")

    dependencies.get_tool_registry.cache_clear()
    dependencies.get_skill_registry.cache_clear()
    dependencies.get_agent.cache_clear()

    yield memory_dir

    dependencies.get_tool_registry.cache_clear()
    dependencies.get_skill_registry.cache_clear()
    dependencies.get_agent.cache_clear()


@pytest.fixture(autouse=True)
def isolated_memory(temp_memory_dir):
    return temp_memory_dir


@pytest.fixture
def registry():
    from void.core.registry import ToolRegistry

    return ToolRegistry()
