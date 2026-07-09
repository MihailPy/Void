from __future__ import annotations

from void.core import activity_history
from void.core.types import AgentAction
from void.tools.builtin import build_registry


def test_activity_logging_listing_latest_and_clear():
    first = activity_history.log_activity(
        "project_command",
        "success",
        "Ran verify for Void",
        {"project": {"id": "void", "name": "Void"}, "command_key": "verify", "cwd": "."},
    )
    second = activity_history.log_activity(
        "git",
        "failure",
        "Failed to create Git commit",
        {"operation": "commit"},
    )

    recent = activity_history.list_recent()

    assert recent[0]["id"] == second["id"]
    assert recent[1]["id"] == first["id"]
    assert activity_history.get_last_activity()["id"] == second["id"]

    activity_history.clear_history()

    assert activity_history.list_recent() == []
    assert activity_history.get_last_activity() is None


def test_activity_history_trims_to_newest_200():
    for index in range(205):
        activity_history.log_activity(
            "project_command",
            "success",
            f"Activity {index}",
            {"index": index},
        )

    recent = activity_history.list_recent(250)

    assert len(recent) == 200
    assert recent[0]["metadata"]["index"] == 204
    assert recent[-1]["metadata"]["index"] == 5


def test_activity_history_compacts_project_metadata():
    activity = activity_history.log_activity(
        "project_command",
        "success",
        "Ran verify for Void",
        {
            "project": {
                "id": "void",
                "name": "Void",
                "root_path": ".",
                "repo_url": "https://github.com/MihailPy/Void",
                "commands": {"verify": "make verify"},
            },
            "command_key": "verify",
            "cwd": ".",
            "returncode": 0,
        },
    )

    assert activity["metadata"]["project"] == {"id": "void", "name": "Void"}
    assert activity["metadata"]["command_key"] == "verify"
    assert activity["metadata"]["returncode"] == 0


def test_activity_tools_are_registered_and_clear_requires_approval():
    registry = build_registry()

    assert registry.get("list_recent_activity").risk_level == "read"
    replay_tool = registry.get("repeat_last_activity")
    assert replay_tool.risk_level == "write"
    assert replay_tool.requires_confirmation is False
    clear_tool = registry.get("clear_activity_history")
    assert clear_tool.risk_level == "write"
    assert clear_tool.requires_confirmation is True

    activity_history.log_activity("git", "success", "Created Git commit", {"operation": "commit"})
    result = registry.execute(
        AgentAction("clear_activity_history", {}, "Test clear activity history.")
    )

    assert result.ok is True
    assert "approval" in result.content.lower()
    assert activity_history.list_recent()


def test_repeat_last_activity_rejects_unsupported_action():
    registry = build_registry()
    activity_history.log_activity(
        "git",
        "success",
        "Created Git commit",
        {"operation": "commit"},
    )

    result = registry.execute(AgentAction("repeat_last_activity", {}, "Test repeat."))

    assert result.ok is True
    assert result.content == "Replay is not supported for this action."
