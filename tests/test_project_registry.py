from __future__ import annotations

from typing import Any

from void.core import activity_history, project_context
from void.core.permissions import approve, clear_approval, list_approvals
from void.core.router import Router
from void.core.types import AgentAction
from void.tools.builtin import build_registry


def _save_registry() -> None:
    project_context.save_project_context(
        {
            "current_project": "void",
            "projects": [
                {
                    "id": "void",
                    "name": "Void",
                    "aliases": ["void"],
                    "root_path": ".",
                    "repo_url": "https://github.com/MihailPy/Void",
                    "commands": {"verify": "make verify"},
                    "workspace": {
                        "terminal": {
                            "app": "terminal",
                            "command": "cd {root} && nvim .",
                            "custom_flag": "keep",
                        },
                        "custom_target": {"enabled": True},
                    },
                    "unknown_project": {"keep": True},
                },
                {
                    "id": "docs",
                    "name": "Docs",
                    "aliases": ["manual"],
                    "root_path": "docs",
                    "repo_url": "",
                    "commands": {},
                },
            ],
        }
    )


def _approve_latest(registry):
    approval = list_approvals()[0]
    action = approve(approval["id"])
    assert action is not None
    result = registry.execute(action, bypass_confirmation=True)
    clear_approval(approval["id"])
    return result


def test_project_registry_create_requires_one_approval_write_and_activity(monkeypatch):
    _save_registry()
    registry = build_registry()
    original_save = project_context.save_project_context
    save_calls: list[dict[str, Any]] = []

    def tracking_save(payload):
        save_calls.append(payload)
        return original_save(payload)

    monkeypatch.setattr(project_context, "save_project_context", tracking_save)
    response = registry.execute(
        AgentAction(
            "create_project",
            {
                "project": {
                    "id": "api",
                    "name": "API",
                    "aliases": ["backend"],
                    "root_path": "api",
                    "repo_url": "",
                    "commands": {"test": "pytest"},
                    "workspace": {"browser": {"app": "Safari"}},
                }
            },
            "Create project:\n\nProject: API\nRoot path: api",
        )
    )

    assert response.ok is True
    assert len(list_approvals()) == 1
    assert save_calls == []

    approved = _approve_latest(registry)

    assert approved.ok is True
    assert len(save_calls) == 1
    assert project_context.get_project("api")["name"] == "API"
    activities = activity_history.list_recent()
    assert len(activities) == 1
    assert activities[0]["activity_type"] == "project_create"


def test_project_registry_update_batches_and_preserves_unknown_fields(monkeypatch):
    _save_registry()
    registry = build_registry()
    original_save = project_context.save_project_context
    save_calls = []

    def tracking_save(payload):
        save_calls.append(payload)
        return original_save(payload)

    monkeypatch.setattr(project_context, "save_project_context", tracking_save)
    response = registry.execute(
        AgentAction(
            "update_project",
            {
                "project_id": "void",
                "project": {
                    "id": "void-renamed",
                    "name": "Void Renamed",
                    "root_path": ".",
                    "aliases": ["void-app"],
                    "commands": {"verify": "make verify", "build": "npm run build"},
                    "workspace": {"terminal": {"app": "terminal"}},
                },
            },
            "test",
        )
    )
    assert response.ok is True
    approved = _approve_latest(registry)

    assert approved.ok is True
    assert len(save_calls) == 1
    project = project_context.get_project("void-renamed")
    assert project["unknown_project"] == {"keep": True}
    assert project["workspace"]["terminal"]["custom_flag"] == "keep"
    assert project["workspace"]["custom_target"] == {"enabled": True}
    assert project_context.load_project_context()["current_project"] == "void-renamed"
    activities = activity_history.list_recent()
    assert len(activities) == 1
    assert activities[0]["activity_type"] == "project_update"


def test_project_registry_delete_rules_and_current_switch():
    _save_registry()
    registry = build_registry()

    denied = registry.execute(
        AgentAction("delete_project", {"project_id": "void"}, "test")
    )
    assert denied.ok is False
    assert "current project" in denied.content
    assert list_approvals() == []

    response = registry.execute(
        AgentAction(
            "delete_project",
            {"project_id": "void", "confirm_current": True},
            "test",
        )
    )
    assert response.ok is True
    approved = _approve_latest(registry)

    assert approved.ok is True
    payload = project_context.load_project_context()
    assert payload["current_project"] == "docs"
    assert [project["id"] for project in payload["projects"]] == ["docs"]
    assert activity_history.get_last_activity()["activity_type"] == "project_delete"

    denied_last = registry.execute(
        AgentAction(
            "delete_project",
            {"project_id": "docs", "confirm_current": True},
            "test",
        )
    )
    assert denied_last.ok is False
    assert "last project" in denied_last.content


def test_project_registry_duplicate_draft_saved_as_duplicate_activity():
    _save_registry()
    registry = build_registry()

    draft = registry.execute(
        AgentAction("duplicate_project", {"project_id": "void"}, "test")
    )
    assert draft.ok is True
    assert project_context.find_project("void-copy") is None

    response = registry.execute(
        AgentAction(
            "create_project",
            {
                "project": draft.data["project"],
                "duplicate_source_id": draft.data["source_project_id"],
            },
            "test",
        )
    )
    assert response.ok is True
    approved = _approve_latest(registry)

    assert approved.ok is True
    copy = project_context.get_project("void-copy")
    assert copy["commands"] == {"verify": "make verify"}
    assert copy["aliases"] == ["void"]
    assert copy["workspace"]["terminal"]["custom_flag"] == "keep"
    assert activity_history.get_last_activity()["activity_type"] == "project_duplicate"


def test_project_registry_validation_before_approval_and_rejection_unchanged():
    _save_registry()
    registry = build_registry()

    invalid = registry.execute(
        AgentAction(
            "create_project",
            {
                "project": {
                    "id": "bad id",
                    "name": "Bad",
                    "root_path": ".",
                }
            },
            "test",
        )
    )
    assert invalid.ok is False
    assert list_approvals() == []

    valid = registry.execute(
        AgentAction(
            "create_project",
            {"project": {"id": "api", "name": "API", "root_path": "."}},
            "test",
        )
    )
    assert valid.ok is True
    approval_id = list_approvals()[0]["id"]
    clear_approval(approval_id)
    assert project_context.find_project("api") is None


def test_project_registry_duplicate_alias_validation_rejected():
    _save_registry()
    registry = build_registry()
    result = registry.execute(
        AgentAction(
            "create_project",
            {
                "project": {
                    "id": "api",
                    "name": "API",
                    "root_path": ".",
                    "aliases": ["api", "API"],
                }
            },
            "test",
        )
    )
    assert result.ok is False
    assert "Duplicate alias" in result.content
    assert list_approvals() == []


def test_project_export_current_all_and_unknown_fields():
    _save_registry()
    registry = build_registry()

    current = registry.execute(AgentAction("export_project", {"current": True}, "test"))
    all_projects = registry.execute(AgentAction("export_projects", {}, "test"))

    assert current.ok is True
    assert current.data["export"]["version"] == 1
    assert current.data["export"]["projects"][0]["unknown_project"] == {"keep": True}
    assert all_projects.ok is True
    assert [project["id"] for project in all_projects.data["export"]["projects"]] == [
        "void",
        "docs",
    ]
    activities = activity_history.list_recent()
    assert activities[0]["activity_type"] == "project_export"


def test_project_import_validate_replace_rename_skip_and_unknown_preservation(monkeypatch):
    _save_registry()
    registry = build_registry()
    source = {
        "version": 1,
        "projects": [
            {
                "id": "api",
                "name": "API",
                "aliases": ["backend"],
                "root_path": "api",
                "repo_url": "",
                "commands": {"test": "pytest"},
                "workspace": {"terminal": {"app": "terminal", "command": "cd {root}"}},
                "unknown": {"survives": True},
            },
            {
                "id": "docs",
                "name": "Docs Imported",
                "aliases": ["manuals"],
                "root_path": "imported-docs",
            },
        ],
    }

    skip_preview = registry.execute(
        AgentAction(
            "validate_project_import",
            {"source": source, "resolution": "skip"},
            "test",
        )
    )
    assert skip_preview.ok is True
    assert skip_preview.data["preview"]["counts"] == {
        "projects": 2,
        "creates": 1,
        "updates": 0,
        "skips": 1,
    }

    rename_preview = registry.execute(
        AgentAction(
            "validate_project_import",
            {"source": source, "resolution": "rename"},
            "test",
        )
    )
    assert rename_preview.ok is True
    assert rename_preview.data["preview"]["creates"][1]["id"] == "docs-import"

    replace_response = registry.execute(
        AgentAction(
            "import_projects",
            {"source": source, "resolution": "replace"},
            "Import projects.",
        )
    )
    assert replace_response.ok is True
    assert len(list_approvals()) == 1

    original_save = project_context.save_project_context
    save_calls: list[dict[str, Any]] = []

    def tracking_save(payload):
        save_calls.append(payload)
        return original_save(payload)

    monkeypatch.setattr(project_context, "save_project_context", tracking_save)
    approved = _approve_latest(registry)

    assert approved.ok is True
    assert len(save_calls) == 1
    assert project_context.get_project("api")["unknown"] == {"survives": True}
    assert project_context.get_project("docs")["name"] == "Docs Imported"
    activities = activity_history.list_recent()
    import_activities = [
        activity for activity in activities if activity["activity_type"] == "project_import"
    ]
    assert len(import_activities) == 1
    assert import_activities[0]["metadata"]["creates"] == 1
    assert import_activities[0]["metadata"]["updates"] == 1


def test_project_import_validation_collects_errors_and_rejection_writes_nothing(monkeypatch):
    _save_registry()
    registry = build_registry()

    invalid = registry.execute(
        AgentAction(
            "validate_project_import",
            {
                "source": {
                    "projects": [
                        {"id": "bad id", "name": "Bad", "root_path": "."},
                        {
                            "id": "api",
                            "name": "API",
                            "root_path": ".",
                            "aliases": ["x", "X"],
                        },
                        {
                            "id": "web",
                            "name": "Web",
                            "root_path": ".",
                            "workspace": {
                                "terminal": {
                                    "app": "unknown",
                                    "command": "cd .",
                                }
                            },
                        },
                    ]
                }
            },
            "test",
        )
    )

    assert invalid.ok is False
    assert "bad id" in invalid.content
    assert "Duplicate alias" in invalid.content
    assert "terminal app" in invalid.content
    assert "must contain {root}" in invalid.content
    assert list_approvals() == []

    valid = registry.execute(
        AgentAction(
            "import_projects",
            {
                "source": {"projects": [{"id": "api", "name": "API", "root_path": "."}]},
                "resolution": "skip",
            },
            "Import projects.",
        )
    )
    assert valid.ok is True
    approval_id = list_approvals()[0]["id"]
    save_calls: list[dict[str, Any]] = []

    def tracking_save(payload):
        save_calls.append(payload)
        return payload

    monkeypatch.setattr(project_context, "save_project_context", tracking_save)
    clear_approval(approval_id)

    assert save_calls == []
    assert project_context.find_project("api") is None
    assert not [
        activity
        for activity in activity_history.list_recent()
        if activity["activity_type"] == "project_import"
    ]


def test_project_registry_router_phrases_and_clarification():
    router = Router()

    assert router.route("Create project named API").action.action == "create_project"
    assert router.route("Создай проект API").action.action == "create_project"
    assert router.route("Delete project docs").action.action == "delete_project"
    assert router.route("Удали проект docs").action.action == "delete_project"
    assert router.route("Duplicate project docs").action.action == "duplicate_project"
    assert router.route("Дублируй проект docs").action.action == "duplicate_project"
    assert router.route("Rename project docs to Docs 2").action.action == "update_project"
    assert router.route("Переименуй проект docs в Docs 2").action.action == "update_project"
    assert router.route("Export current project").action.action == "export_project"
    assert router.route("Export all projects").action.action == "export_projects"
    assert router.route("Export project docs").action.action == "export_project"
    assert router.route("Экспортируй проект").action.action == "export_project"
    assert router.route("Экспортируй все проекты").action.action == "export_projects"
    assert router.route("Импортируй проект").clarification.context["original_action"] == "import_projects"
    assert router.route("Импортируй проекты").clarification.context["original_action"] == "import_projects"
    assert router.route("Проверь импорт проектов").clarification.context["original_action"] == "validate_project_import"

    clarification = router.route("Delete project")
    assert clarification.clarification is not None
    assert clarification.clarification.context["original_action"] == "delete_project"
