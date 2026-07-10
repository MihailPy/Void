from void.core.agent import Agent
from void.core import clarification
from void.core.clarification import (
    clear_pending_clarification,
    create_clarification,
    ensure_clarification_storage,
    has_pending_clarification,
    load_pending_clarification,
    resolve_clarification,
)
from void.core.registry import ToolRegistry
from void.core.router import Router
from void.tools import project_tools


def _project_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for definition in project_tools.definitions():
        registry.register(definition)
    return registry


def test_clarification_storage_creation():
    assert not clarification.CLARIFICATION_PATH.exists()

    ensure_clarification_storage()

    assert clarification.CLARIFICATION_PATH.exists()
    assert load_pending_clarification() is None


def test_create_and_resolve_clarification():
    pending = create_clarification(
        "Which project do you want to open?",
        "project_selection",
        {"original_action": "open_project_repo", "missing_field": "project"},
    )

    assert has_pending_clarification() is True
    assert pending["id"].startswith("clar_")
    assert load_pending_clarification()["question"] == "Which project do you want to open?"

    resolved = resolve_clarification("Void")

    assert resolved is not None
    assert resolved["answer"] == "Void"
    assert has_pending_clarification() is False


def test_clear_pending_clarification():
    create_clarification(
        "Which project?",
        "project_selection",
        {"original_action": "set_current_project"},
    )

    clear_pending_clarification()

    assert load_pending_clarification() is None


def test_router_open_project_github_requests_clarification():
    route = Router().route("open project github")

    assert route.matched is True
    assert route.action is None
    assert route.clarification is not None
    assert route.clarification.clarification_type == "project_selection"
    assert route.clarification.context["original_action"] == "open_project_repo_in_browser"


def test_router_run_project_command_requests_clarification():
    route = Router().route("run project command")

    assert route.matched is True
    assert route.action is None
    assert route.clarification is not None
    assert route.clarification.clarification_type == "command_selection"
    assert route.clarification.context["missing_field"] == "command_key"
    assert "test" in route.clarification.context["available_commands"]


def test_router_switch_project_requests_clarification():
    route = Router().route("переключи проект")

    assert route.matched is True
    assert route.action is None
    assert route.clarification is not None
    assert route.clarification.clarification_type == "project_selection"
    assert route.clarification.context["original_action"] == "set_current_project"


def test_agent_resumes_project_selection_to_browser_approval():
    agent = Agent(registry=_project_registry())

    first = agent.handle_result("open project github")
    second = agent.handle_result("Void")

    assert first.kind == "clarification_request"
    assert second.kind == "tool_call"
    assert "requires approval" in second.content.lower()
    assert has_pending_clarification() is False


def test_action_from_resolved_clarification_opens_project_repo_in_browser():
    resolved = {
        "type": "project_selection",
        "context": {"original_action": "open_project_repo_in_browser"},
        "answer": "Void",
    }

    action = clarification.action_from_resolved_clarification(resolved)

    assert action is not None
    assert action.action == "open_project_repo_in_browser"
    assert action.arguments == {"project": "Void"}


def test_agent_resumes_command_selection_with_approval():
    agent = Agent(registry=_project_registry())

    first = agent.handle_result("run project command")
    second = agent.handle_result("test")

    assert first.kind == "clarification_request"
    assert second.kind == "tool_call"
    assert "requires approval" in second.content.lower()
    assert has_pending_clarification() is False


def test_agent_resumes_visible_command_selection_with_approval():
    agent = Agent(registry=_project_registry())

    first = agent.handle_result("run command in terminal")
    second = agent.handle_result("test")

    assert first.kind == "clarification_request"
    assert first.clarification is not None
    assert first.clarification.context["original_action"] == "run_project_command_visible"
    assert second.kind == "tool_call"
    assert second.tool_result is not None
    assert second.tool_result.data is not None
    assert second.tool_result.data["action"] == "run_project_command_visible"
    assert "requires approval" in second.content.lower()
    assert has_pending_clarification() is False
