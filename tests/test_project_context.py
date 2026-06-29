from void.core import project_context
from void.core.permissions import approve, clear_approval, list_approvals
from void.core.types import AgentAction
from void.tools.builtin import build_registry


def test_default_project_context_created(temp_memory_dir):
    path = temp_memory_dir / "projects.json"
    assert not path.exists()

    payload = project_context.load_project_context()

    assert path.exists()
    assert payload["current_project"] == "void"
    assert payload["projects"][0]["id"] == "void"
    assert payload["projects"][0]["repo_url"] == "https://github.com/MihailPy/Void"


def test_find_project_by_id_name_alias():
    assert project_context.find_project("void")["name"] == "Void"
    assert project_context.find_project("VOID")["id"] == "void"
    assert project_context.find_project("MihailPy/Void")["id"] == "void"
    assert project_context.find_project("missing") is None


def test_set_current_project_by_alias(temp_memory_dir):
    project_context.save_project_context(
        {
            "current_project": "void",
            "projects": [
                {
                    "id": "void",
                    "name": "Void",
                    "aliases": ["MihailPy/Void"],
                    "root_path": ".",
                    "repo_url": "https://github.com/MihailPy/Void",
                    "commands": {"verify": "make verify"},
                },
                {
                    "id": "notes",
                    "name": "Notes",
                    "aliases": ["personal notes"],
                    "root_path": "../notes",
                    "repo_url": "",
                    "commands": {},
                },
            ],
        }
    )

    result = project_context.set_current_project("personal notes")

    assert result["ok"] is True
    assert project_context.load_project_context()["current_project"] == "notes"
    assert project_context.get_current_project()["name"] == "Notes"


def test_invalid_project_id_rejected():
    try:
        project_context.save_project_context(
            {
                "current_project": "bad id",
                "projects": [{"id": "bad id", "name": "Bad"}],
            }
        )
    except ValueError as error:
        assert "Project id" in str(error)
    else:
        raise AssertionError("Expected invalid project id to fail")


def test_project_tools_registered_with_metadata():
    registry = build_registry()

    expected = {
        "list_projects": ("project", "read", False),
        "get_current_project": ("project", "read", False),
        "describe_current_project": ("project", "read", False),
        "list_project_commands": ("project", "read", False),
        "run_project_command": ("project", "write", True),
        "set_current_project": ("project", "write", True),
    }

    for name, (category, risk_level, requires_confirmation) in expected.items():
        tool = registry.get(name)
        assert tool is not None
        assert tool.category == category
        assert tool.risk_level == risk_level
        assert tool.requires_confirmation is requires_confirmation


def test_set_current_project_tool_creates_approval():
    registry = build_registry()

    result = registry.execute(
        AgentAction("set_current_project", {"project": "Void"}, "test")
    )

    assert result.ok is True
    assert "approval" in result.content.lower()
    approvals = list_approvals()
    assert approvals[0]["action"] == "set_current_project"
    assert approvals[0]["category"] == "project"
    assert approvals[0]["risk_level"] == "write"


def test_set_current_project_switches_after_approval():
    project_context.save_project_context(
        {
            "current_project": "void",
            "projects": [
                {"id": "void", "name": "Void", "aliases": [], "root_path": "."},
                {"id": "notes", "name": "Notes", "aliases": ["notes-app"]},
            ],
        }
    )
    registry = build_registry()

    result = registry.execute(
        AgentAction("set_current_project", {"project": "notes-app"}, "test")
    )
    approval_id = list_approvals()[0]["id"]
    action = approve(approval_id)

    assert result.ok is True
    assert action is not None
    approved_result = registry.execute(action, bypass_confirmation=True)
    clear_approval(approval_id)

    assert approved_result.ok is True
    assert project_context.get_current_project()["id"] == "notes"
