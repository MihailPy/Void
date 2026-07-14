from __future__ import annotations

from typing import Any

import pytest

from void.core import activity_history, project_context, workspace_preferences
from void.core.permissions import approve, clear_approval, list_approvals
from void.core.types import AgentAction
from void.tools.builtin import build_registry


def _save_project(workspace: dict[str, Any] | None = None) -> None:
    project: dict[str, Any] = {
        "id": "void",
        "name": "Void",
        "aliases": ["void", "MihailPy/Void"],
        "root_path": ".",
        "repo_url": "https://github.com/MihailPy/Void",
        "commands": {},
    }
    if workspace is not None:
        project["workspace"] = workspace
    project_context.save_project_context(
        {
            "current_project": "void",
            "projects": [project],
        }
    )


def _approve_latest(registry):
    approval = list_approvals()[0]
    action = approve(approval["id"])
    assert action is not None
    result = registry.execute(action, bypass_confirmation=True)
    clear_approval(approval["id"])
    return result


def test_workspace_preferences_validation_normalizes_supported_values():
    assert workspace_preferences.validate_preference("terminal", "app", "iTerm2") == "iterm2"
    assert workspace_preferences.validate_preference("terminal", "reuse_existing", "YES") == "true"
    assert workspace_preferences.validate_preference("terminal", "open_mode", "Window") == "window"
    assert (
        workspace_preferences.validate_preference("terminal", "window_bounds", "100, 80, 1500, 950")
        == "100,80,1500,950"
    )
    assert workspace_preferences.validate_preference("browser", "app", "Safari") == "Safari"
    assert workspace_preferences.validate_preference("file_manager", "app", "Finder") == "Finder"


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        ("terminal", "app", "warp", "terminal app"),
        ("terminal", "command", "nvim .", "{root}"),
        ("terminal", "command", "", "must not be empty"),
        ("terminal", "window_bounds", "100,80,50,950", "left < right"),
        ("terminal", "window_bounds", "100,80,1500", "format"),
        ("terminal", "reuse_existing", "sometimes", "reuse_existing"),
        ("terminal", "open_mode", "pane", "open_mode"),
        ("browser", "app", "", "must not be empty"),
    ],
)
def test_workspace_preferences_validation_rejects_invalid_values(
    section: str,
    field: str,
    value: str,
    message: str,
):
    with pytest.raises(ValueError, match=message):
        workspace_preferences.validate_preference(section, field, value)


def test_workspace_preferences_update_preserves_unknown_keys_and_saves():
    _save_project(
        {
            "terminal": {
                "app": "terminal",
                "command": "cd {root} && nvim .",
                "custom_key": "keep",
            },
            "custom_target": {"custom": "value"},
        }
    )

    result = workspace_preferences.update_workspace_preference(
        None,
        "terminal",
        "profile",
        "Development",
    )

    assert result["new_value"] == "Development"
    project = project_context.get_current_project()
    assert project["workspace"]["terminal"]["custom_key"] == "keep"
    assert project["workspace"]["custom_target"]["custom"] == "value"
    assert project["workspace"]["terminal"]["profile"] == "Development"
    latest = activity_history.get_last_activity()
    assert latest["activity_type"] == "workspace_preferences_update"
    assert latest["metadata"]["changes"] == [
        {
            "section": "terminal",
            "field": "profile",
            "old_value": None,
            "new_value": "Development",
        }
    ]
    assert "replay" not in latest["metadata"]


def test_workspace_preferences_batch_saves_once_and_logs_once(monkeypatch):
    _save_project(
        {
            "terminal": {
                "app": "terminal",
                "command": "cd {root} && nvim .",
            },
            "browser": {"app": "Default"},
        }
    )
    original_save = project_context.save_project_context
    save_calls = []

    def tracking_save(payload):
        save_calls.append(payload)
        return original_save(payload)

    monkeypatch.setattr(project_context, "save_project_context", tracking_save)

    result = workspace_preferences.update_workspace_preferences(
        None,
        [
            {"section": "terminal", "field": "open_mode", "value": "tab"},
            {"section": "browser", "field": "app", "value": "Safari"},
        ],
    )

    assert len(save_calls) == 1
    assert result["changes"] == [
        {
            "section": "terminal",
            "field": "open_mode",
            "old_value": None,
            "new_value": "tab",
        },
        {
            "section": "browser",
            "field": "app",
            "old_value": "Default",
            "new_value": "Safari",
        },
    ]
    project = project_context.get_current_project()
    assert project["workspace"]["terminal"]["open_mode"] == "tab"
    assert project["workspace"]["browser"]["app"] == "Safari"
    activities = activity_history.list_recent()
    assert len(activities) == 1
    assert activities[0]["activity_type"] == "workspace_preferences_update"
    assert activities[0]["metadata"]["changes"] == result["changes"]


def test_workspace_preferences_invalid_second_change_saves_nothing():
    _save_project(
        {
            "terminal": {
                "app": "terminal",
                "command": "cd {root} && nvim .",
            },
        }
    )

    with pytest.raises(ValueError, match="open_mode"):
        workspace_preferences.update_workspace_preferences(
            None,
            [
                {"section": "terminal", "field": "profile", "value": "Development"},
                {"section": "terminal", "field": "open_mode", "value": "pane"},
            ],
        )

    project = project_context.get_current_project()
    assert "profile" not in project["workspace"]["terminal"]
    assert activity_history.get_last_activity() is None


def test_workspace_preferences_duplicate_and_empty_changes_are_rejected():
    _save_project({"browser": {"app": "Default"}})

    with pytest.raises(ValueError, match="at least one"):
        workspace_preferences.update_workspace_preferences(None, [])

    with pytest.raises(ValueError, match="Duplicate"):
        workspace_preferences.update_workspace_preferences(
            None,
            [
                {"section": "browser", "field": "app", "value": "Safari"},
                {"section": "browser", "field": "app", "value": "Chrome"},
            ],
        )

    assert project_context.get_current_project()["workspace"]["browser"]["app"] == "Default"


def test_workspace_preferences_tool_batch_update_requires_one_approval():
    _save_project({"browser": {"app": "Default"}})
    registry = build_registry()

    response = registry.execute(
        AgentAction(
            "update_workspace_preferences",
            {
                "changes": [
                    {"section": "browser", "field": "app", "value": "Safari"},
                    {"section": "terminal", "field": "profile", "value": "Development"},
                ]
            },
            "test",
        )
    )

    assert response.ok is True
    assert "approval" in response.content.lower()
    approval = list_approvals()[0]
    assert approval["action"] == "update_workspace_preferences"
    assert approval["arguments"] == {
        "changes": [
            {"section": "browser", "field": "app", "value": "Safari"},
            {"section": "terminal", "field": "profile", "value": "Development"},
        ]
    }
    assert approval["category"] == "project"
    assert approval["risk_level"] == "write"
    assert project_context.get_current_project()["workspace"]["browser"]["app"] == "Default"

    result = _approve_latest(registry)

    assert result.ok is True
    assert project_context.get_current_project()["workspace"]["browser"]["app"] == "Safari"
    assert project_context.get_current_project()["workspace"]["terminal"]["profile"] == "Development"


def test_workspace_preferences_tool_legacy_single_field_still_works():
    _save_project({"browser": {"app": "Default"}})
    registry = build_registry()

    registry.execute(
        AgentAction(
            "update_workspace_preferences",
            {"section": "browser", "field": "app", "value": "Safari"},
            "test",
        )
    )
    result = _approve_latest(registry)

    assert result.ok is True
    assert result.data is not None
    assert result.data["changes"] == [
        {
            "section": "browser",
            "field": "app",
            "old_value": "Default",
            "new_value": "Safari",
        }
    ]
