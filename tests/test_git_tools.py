from void.core import activity_history
from void.core.permissions import approve, clear_approval, list_approvals
from void.core.types import AgentAction
from void.tools.builtin import build_registry
from void.tools.git_tools import SAFETY_ERROR, run_git_command


def test_run_git_command_blocks_dangerous_commands():
    for command in ("push", "pull", "reset", "checkout", "merge", "rebase", "clean"):
        result = run_git_command([command])

        assert result.ok is False
        assert result.content == SAFETY_ERROR


def test_git_tools_registered():
    registry = build_registry()

    for name in (
        "git_status",
        "git_diff",
        "git_log",
        "git_current_branch",
        "git_suggest_commit_message",
        "git_commit",
    ):
        tool = registry.get(name)
        assert tool is not None
        assert tool.terminal is True


def test_git_commit_requires_confirmation():
    registry = build_registry()
    tool = registry.get("git_commit")

    assert tool is not None
    assert tool.requires_confirmation is True

    result = registry.execute(
        AgentAction(
            "git_commit",
            {"message": "test"},
            "test",
        )
    )
    assert result.ok is True
    assert "approval" in result.content.lower()


def test_git_commit_failure_logs_activity_after_approval():
    registry = build_registry()
    registry.execute(AgentAction("git_commit", {"message": ""}, "test"))
    approval_id = list_approvals()[0]["id"]
    action = approve(approval_id)

    assert action is not None
    result = registry.execute(action, bypass_confirmation=True)
    clear_approval(approval_id)

    assert result.ok is False
    latest = activity_history.get_last_activity()
    assert latest is not None
    assert latest["activity_type"] == "git"
    assert latest["status"] == "failure"
    assert latest["metadata"]["operation"] == "commit"
