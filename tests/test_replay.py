from __future__ import annotations

import sys
from typing import Any

from void.core import activity_history, browser_sessions, project_commands, project_context
from void.core.permissions import approve, clear_approval, list_approvals
from void.core.router import Router
from void.core.types import AgentAction
from void.tools.builtin import build_registry


def _save_projects(
    projects: list[dict[str, Any]],
    current_project: str = "void",
) -> None:
    project_context.save_project_context(
        {
            "current_project": current_project,
            "projects": projects,
        }
    )


def _project(project_id: str = "void", commands: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "id": project_id,
        "name": project_id.title(),
        "aliases": [project_id],
        "root_path": ".",
        "repo_url": f"https://github.com/MihailPy/{project_id.title()}",
        "commands": commands or {},
    }


def _approve_latest(registry):
    approval = list_approvals()[0]
    action = approve(approval["id"])
    assert action is not None
    result = registry.execute(action, bypass_confirmation=True)
    clear_approval(approval["id"])
    return result


def test_replay_command_requires_approval_and_creates_history_entry():
    command = f"{sys.executable} -c \"print('replayed')\""
    _save_projects([_project(commands={"verify": command})])
    registry = build_registry()

    activity_history.log_activity(
        "project_command",
        "success",
        "Ran verify for Void",
        {"command_key": "verify", "timeout_seconds": 5},
    )

    replay_request = registry.execute(AgentAction("repeat_last_activity", {}, "test"))

    assert replay_request.ok is True
    assert "approval" in replay_request.content.lower()
    assert list_approvals()[0]["action"] == "run_project_command"
    assert list_approvals()[0]["arguments"] == {
        "command_key": "verify",
        "timeout_seconds": 5,
    }

    replay_result = _approve_latest(registry)

    assert replay_result.ok is True
    assert "replayed" in replay_result.content
    recent = activity_history.list_recent()
    assert recent[0]["activity_type"] == "project_command"
    assert recent[0]["metadata"]["command_key"] == "verify"
    assert recent[1]["summary"] == "Ran verify for Void"


def test_replay_browser_action_requires_approval_and_reopens_project_repo(monkeypatch):
    _save_projects([_project("void")])
    opened: list[tuple[str, str]] = []

    def fake_open_session(url: str, mode: str) -> dict[str, Any]:
        opened.append((url, mode))
        return {
            "session_id": f"session-{len(opened)}",
            "mode": mode,
            "url": url,
            "title": "Repo",
        }

    monkeypatch.setattr(browser_sessions, "open_session", fake_open_session)
    registry = build_registry()

    first = registry.execute(
        AgentAction(
            "open_project_repo_in_browser",
            {"project": "void", "mode": "visible"},
            "test",
        )
    )
    assert first.ok is True
    _approve_latest(registry)

    replay_request = registry.execute(AgentAction("repeat_last_activity", {}, "test"))

    assert replay_request.ok is True
    assert list_approvals()[0]["action"] == "open_project_repo_in_browser"
    assert list_approvals()[0]["arguments"] == {"project": "void", "mode": "visible"}

    replay_result = _approve_latest(registry)

    assert replay_result.ok is True
    assert opened == [
        ("https://github.com/MihailPy/Void", "visible"),
        ("https://github.com/MihailPy/Void", "visible"),
    ]
    assert activity_history.list_recent()[0]["activity_type"] == "browser_session_open"


def test_replay_repo_open_requires_approval_with_compact_project_metadata():
    _save_projects([_project("void")])
    registry = build_registry()
    activity_history.log_activity(
        "repo_open",
        "success",
        "Resolved repository for Void",
        {
            "project": {
                "id": "void",
                "name": "Void",
                "root_path": ".",
                "repo_url": "https://github.com/MihailPy/Void",
            },
            "url": "https://github.com/MihailPy/Void",
        },
    )

    replay_request = registry.execute(AgentAction("repeat_last_activity", {}, "test"))

    assert replay_request.ok is True
    assert "https://github.com/MihailPy/Void" in replay_request.content
    assert replay_request.data["replayed_activity_id"]
    assert replay_request.data["replay_action"] == "open_project_repo"
    assert list_approvals() == []
    assert activity_history.get_last_activity()["metadata"]["project"] == {
        "id": "void",
        "name": "Void",
    }


def test_replay_project_switch_requires_approval_and_switches_again():
    _save_projects([_project("void"), _project("other")], current_project="void")
    registry = build_registry()
    activity_history.log_activity(
        "project_switch",
        "success",
        "Switched project to Other",
        {"project": {"id": "other", "name": "Other"}},
    )

    replay_request = registry.execute(AgentAction("repeat_last_activity", {}, "test"))

    assert replay_request.ok is True
    assert list_approvals()[0]["action"] == "set_current_project"
    assert list_approvals()[0]["arguments"] == {"project": "other"}

    replay_result = _approve_latest(registry)

    assert replay_result.ok is True
    assert project_context.get_current_project()["id"] == "other"
    assert activity_history.get_last_activity()["activity_type"] == "project_switch"


def test_unsupported_replay_fails_gracefully():
    registry = build_registry()
    activity_history.log_activity("git", "success", "Created Git commit", {"operation": "commit"})

    result = registry.execute(AgentAction("repeat_last_activity", {}, "test"))

    assert result.ok is True
    assert result.content == "Replay is not supported for this action."
    assert list_approvals() == []


def test_replay_without_activity_reports_no_previous_action():
    registry = build_registry()

    result = registry.execute(AgentAction("repeat_last_activity", {}, "test"))

    assert result.ok is True
    assert result.content == "No previous action found."
    assert result.data == {"activity": None}


def test_replay_visible_terminal_action_requires_approval(monkeypatch):
    _save_projects([_project(commands={"test": "python -V"})])
    launches: list[tuple[str, str]] = []

    def fake_launch(command: str, cwd: str) -> dict[str, Any]:
        launches.append((command, cwd))
        return {
            "ok": True,
            "terminal_type": "fake-terminal",
            "command": command,
            "cwd": cwd,
            "pid": 123,
            "message": "Launched.",
        }

    monkeypatch.setattr(project_commands.terminal_runner, "launch_terminal_command", fake_launch)
    registry = build_registry()
    activity_history.log_activity(
        "terminal",
        "success",
        "Launched test in visible terminal",
        {"command_key": "test"},
    )

    replay_request = registry.execute(AgentAction("repeat_last_activity", {}, "test"))

    assert replay_request.ok is True
    assert list_approvals()[0]["action"] == "run_project_command_visible"

    replay_result = _approve_latest(registry)

    assert replay_result.ok is True
    assert launches[0][0] == "python -V"
    assert activity_history.get_last_activity()["activity_type"] == "terminal"


def test_router_replay_phrases():
    for phrase in (
        "repeat last action",
        "repeat previous action",
        "run that again",
        "do it again",
        "повтори последнее действие",
        "повтори предыдущую команду",
        "сделай это еще раз",
    ):
        route = Router().route(phrase)

        assert route.matched is True
        assert route.action is not None
        assert route.action.action == "repeat_last_activity"
