from __future__ import annotations

import sys

from void.core import activity_history, project_commands, project_context, terminal_runner
from void.core.permissions import approve, clear_approval, list_approvals
from void.core.types import AgentAction
from void.tools.builtin import build_registry


def _save_commands(commands: dict[str, str], root_path: str = ".") -> None:
    project_context.save_project_context(
        {
            "current_project": "void",
            "projects": [
                {
                    "id": "void",
                    "name": "Void",
                    "aliases": ["MihailPy/Void"],
                    "root_path": root_path,
                    "repo_url": "https://github.com/MihailPy/Void",
                    "commands": commands,
                }
            ],
        }
    )


def test_list_project_commands():
    _save_commands({"test": "python -V", "verify": "make verify"})

    result = project_commands.list_project_commands()

    assert result["project"]["id"] == "void"
    assert result["commands"] == {"test": "python -V", "verify": "make verify"}
    assert result["cwd"].endswith("Void")


def test_get_project_command_case_insensitive():
    _save_commands({"TeSt": "python -V"})

    result = project_commands.get_project_command("test")

    assert result["key"] == "TeSt"
    assert result["command"] == "python -V"


def test_run_project_command_captures_result():
    command = f"{sys.executable} -c \"print('ok')\""
    _save_commands({"test": command})

    result = project_commands.run_project_command("TEST", timeout_seconds=5)

    assert result["ok"] is True
    assert result["returncode"] == 0
    assert result["stdout"].strip() == "ok"
    assert result["stderr"] == ""
    assert result["command"] == command
    assert result["project"]["name"] == "Void"


def test_run_project_command_timeout():
    command = f"{sys.executable} -c \"import time; time.sleep(2)\""
    _save_commands({"slow": command})

    result = project_commands.run_project_command("slow", timeout_seconds=1)

    assert result["ok"] is False
    assert result["timed_out"] is True
    assert "timed out" in result["error"]


def test_terminal_supported_macos(monkeypatch):
    monkeypatch.setattr(terminal_runner.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(terminal_runner.shutil, "which", lambda name: "/usr/bin/osascript")

    assert terminal_runner.terminal_supported() is True


def test_terminal_supported_linux_without_emulator(monkeypatch):
    monkeypatch.setattr(terminal_runner.platform, "system", lambda: "Linux")
    monkeypatch.setattr(terminal_runner.shutil, "which", lambda name: None)

    assert terminal_runner.terminal_supported() is False


def test_run_project_command_visible_uses_terminal_runner(monkeypatch):
    _save_commands({"test": "python -V"})
    launches = []

    def fake_launch(command: str, cwd: str) -> dict:
        launches.append((command, cwd))
        return {
            "ok": True,
            "terminal_type": "fake-terminal",
            "command": command,
            "cwd": cwd,
            "pid": 123,
            "message": "Launched command in fake-terminal.",
        }

    monkeypatch.setattr(project_commands.terminal_runner, "launch_terminal_command", fake_launch)

    result = project_commands.run_project_command_visible("test")

    assert result["ok"] is True
    assert result["mode"] == "visible_terminal"
    assert result["command_key"] == "test"
    assert result["terminal"]["terminal_type"] == "fake-terminal"
    assert launches == [("python -V", result["cwd"])]


def test_project_command_not_found_error():
    _save_commands({"test": "python -V"})

    try:
        project_commands.get_project_command("missing")
    except ValueError as error:
        assert "not configured" in str(error)
    else:
        raise AssertionError("Expected missing command to fail")


def test_project_command_cwd_safety():
    _save_commands({"test": "python -V"}, root_path="../outside")

    try:
        project_commands.list_project_commands()
    except ValueError as error:
        assert "Path traversal" in str(error) or "outside" in str(error)
    else:
        raise AssertionError("Expected unsafe project root to fail")


def test_run_project_command_tool_is_approval_gated():
    _save_commands({"test": "python -V"})
    registry = build_registry()

    result = registry.execute(
        AgentAction("run_project_command", {"command_key": "test"}, "test")
    )

    assert result.ok is True
    assert "approval" in result.content.lower()
    approvals = list_approvals()
    assert approvals[0]["action"] == "run_project_command"
    assert approvals[0]["category"] == "project"
    assert approvals[0]["risk_level"] == "write"


def test_run_project_command_visible_tool_is_approval_gated():
    _save_commands({"test": "python -V"})
    registry = build_registry()

    result = registry.execute(
        AgentAction("run_project_command_visible", {"command_key": "test"}, "test")
    )

    assert result.ok is True
    assert "approval" in result.content.lower()
    approvals = list_approvals()
    assert approvals[0]["action"] == "run_project_command_visible"
    assert approvals[0]["category"] == "project"
    assert approvals[0]["risk_level"] == "write"


def test_run_project_command_executes_after_approval():
    _save_commands({"test": f"{sys.executable} -c \"print('approved')\""})
    registry = build_registry()

    result = registry.execute(
        AgentAction("run_project_command", {"command_key": "test"}, "test")
    )
    approval_id = list_approvals()[0]["id"]
    action = approve(approval_id)

    assert result.ok is True
    assert action is not None
    approved_result = registry.execute(action, bypass_confirmation=True)
    clear_approval(approval_id)

    assert approved_result.ok is True
    assert "approved" in approved_result.content
    latest = activity_history.get_last_activity()
    assert latest is not None
    assert latest["activity_type"] == "project_command"
    assert latest["status"] == "success"
    assert latest["metadata"]["command_key"] == "test"


def test_run_project_command_visible_logs_terminal_activity(monkeypatch):
    _save_commands({"test": "python -V"})

    def fake_launch(command: str, cwd: str) -> dict:
        return {
            "ok": True,
            "terminal_type": "fake-terminal",
            "command": command,
            "cwd": cwd,
            "pid": 123,
            "message": "Launched command in fake-terminal.",
        }

    monkeypatch.setattr(project_commands.terminal_runner, "launch_terminal_command", fake_launch)

    registry = build_registry()
    request_result = registry.execute(
        AgentAction("run_project_command_visible", {"command_key": "test"}, "test")
    )
    approval_id = list_approvals()[0]["id"]
    action = approve(approval_id)

    assert request_result.ok is True
    assert action is not None
    approved_result = registry.execute(action, bypass_confirmation=True)
    clear_approval(approval_id)

    assert approved_result.ok is True
    latest = activity_history.get_last_activity()
    assert latest is not None
    assert latest["activity_type"] == "terminal"
    assert latest["metadata"]["terminal_type"] == "fake-terminal"
