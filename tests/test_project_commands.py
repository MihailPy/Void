from __future__ import annotations

import sys

from void.core import project_commands, project_context
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
