from collections.abc import Mapping
import sys
from typing import Any

import anyio
import httpx

from void.api.server import app
from void.__version__ import __version__
from void.core import activity_history
from void.core import project_commands, project_context


async def _request(
    method: str,
    path: str,
    json: Mapping[str, Any] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json)


def request(
    method: str,
    path: str,
    *,
    json: Mapping[str, Any] | None = None,
) -> httpx.Response:
    return anyio.run(_request, method, path, json)


def _save_projects(projects: list[dict[str, Any]], current_project: str = "void") -> None:
    project_context.save_project_context(
        {
            "current_project": current_project,
            "projects": projects,
        }
    )


def _void_project(commands: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "id": "void",
        "name": "Void",
        "aliases": ["void", "MihailPy/Void"],
        "root_path": ".",
        "repo_url": "https://github.com/MihailPy/Void",
        "commands": commands
        if commands is not None
        else {
            "verify": "make verify",
            "test": "make verify",
            "build": "cd web && npm run build",
            "dev": "make web",
        },
    }


def _approval_for(action: str) -> dict[str, Any]:
    approvals_response = request("GET", "/approvals")
    approvals = approvals_response.json()["pending"]
    for approval in approvals:
        if approval["action"] == action:
            return approval
    raise AssertionError(f"Approval not found for action: {action}")


def test_health():
    response = request("GET", "/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["version"] == __version__


def test_error_response_shape_for_missing_approval():
    response = request("POST", "/approvals/missing/approve")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "Approval not found: missing"
    assert payload["message"] == "Approval not found: missing"
    assert payload["result_type"] == "error"
    assert payload["data"] is None


def test_skills():
    response = request("GET", "/skills")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_lifespan_closes_browser_sessions_on_shutdown(monkeypatch):
    calls: list[str] = []

    def close_all_sessions() -> int:
        calls.append("closed")
        return 2

    monkeypatch.setattr(
        "void.api.server.browser_sessions.close_all_sessions",
        close_all_sessions,
    )

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            pass

    anyio.run(run_lifespan)

    assert calls == ["closed"]


def test_lifespan_browser_session_cleanup_failure_warns(monkeypatch, capsys):
    def close_all_sessions() -> int:
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(
        "void.api.server.browser_sessions.close_all_sessions",
        close_all_sessions,
    )

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            pass

    anyio.run(run_lifespan)

    captured = capsys.readouterr()
    assert "WARNING: Failed to close browser sessions during shutdown" in captured.out
    assert "cleanup failed" in captured.out


def test_capabilities():
    response = request("GET", "/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["installed"] == []
    assert payload["requested"] == []
    assert payload["rejected"] == []


def test_activity_endpoints_and_clear_approval():
    activity_history.log_activity(
        "project_command",
        "success",
        "Ran verify for Void",
        {"command_key": "verify"},
    )

    response = request("GET", "/activity")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["activities"][0]["summary"] == "Ran verify for Void"

    latest_response = request("GET", "/activity/latest")
    assert latest_response.status_code == 200
    assert latest_response.json()["activity"]["activity_type"] == "project_command"

    clear_response = request("POST", "/activity/clear")
    assert clear_response.status_code == 200
    clear_payload = clear_response.json()
    assert clear_payload["ok"] is True
    assert clear_payload["result_type"] == "approval"
    assert clear_payload["data"]["action"] == "clear_activity_history"

    assert request("GET", "/activity").json()["activities"]

    approval = _approval_for("clear_activity_history")
    approved = request("POST", f"/approvals/{approval['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["ok"] is True
    assert request("GET", "/activity").json()["activities"] == []


def test_activity_replay_endpoints_create_target_approval():
    activity = activity_history.log_activity(
        "project_command",
        "success",
        "Ran verify for Void",
        {"command_key": "verify", "timeout_seconds": 30},
    )

    latest_response = request("POST", "/activity/replay/latest")
    assert latest_response.status_code == 200
    latest_payload = latest_response.json()
    assert latest_payload["ok"] is True
    assert latest_payload["result_type"] == "approval"
    assert latest_payload["data"]["action"] == "run_project_command"
    assert latest_payload["data"]["arguments"] == {
        "command_key": "verify",
        "timeout_seconds": 30,
    }
    assert latest_payload["data"]["replayed_activity_id"] == activity["id"]

    explicit_response = request("POST", f"/activity/replay/{activity['id']}")
    assert explicit_response.status_code == 200
    explicit_payload = explicit_response.json()
    assert explicit_payload["ok"] is True
    assert explicit_payload["result_type"] == "approval"
    assert explicit_payload["data"]["action"] == "run_project_command"


def test_activity_replay_endpoint_unsupported_action():
    activity = activity_history.log_activity(
        "git",
        "success",
        "Created Git commit",
        {"operation": "commit"},
    )

    response = request("POST", f"/activity/replay/{activity['id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["message"] == "Replay is not supported for this action."
    assert payload["result_type"] == "message"


def test_projects_endpoint():
    response = request("GET", "/projects")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["projects"][0]["id"] == "void"


def test_current_project_endpoint():
    response = request("GET", "/projects/current")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["project"]["name"] == "Void"


def test_describe_current_project_endpoint():
    response = request("GET", "/projects/current/describe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "Current project" in payload["description"]
    assert payload["project"]["id"] == "void"


def test_current_project_commands_endpoint():
    response = request("GET", "/projects/current/commands")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["project"]["id"] == "void"
    assert payload["commands"]["test"] == "make verify"


def test_set_current_project_endpoint_creates_approval():
    response = request("POST", "/projects/current", json={"project": "Void"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "approval" in payload["message"].lower()
    assert payload["result_type"] == "approval"
    assert payload["data"]["action"] == "set_current_project"


def test_run_project_command_endpoint_creates_approval():
    response = request(
        "POST",
        "/projects/current/commands/test/run",
        json={"timeout_seconds": 120},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "approval" in payload["message"].lower()
    assert payload["result_type"] == "approval"


def test_run_project_command_visible_endpoint_creates_approval():
    response = request("POST", "/projects/current/commands/test/run-visible")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "approval" in payload["message"].lower()
    assert payload["result_type"] == "approval"
    assert payload["data"]["action"] == "run_project_command_visible"
    assert payload["data"]["arguments"] == {"command_key": "test"}


def test_open_project_repo_endpoint_creates_approval():
    response = request(
        "POST",
        "/projects/repo/open",
        json={"project": "Void", "mode": "visible"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "approval" in payload["message"].lower()
    assert payload["result_type"] == "approval"

    approvals_response = request("GET", "/approvals")
    approvals = approvals_response.json()["pending"]
    assert approvals[0]["action"] == "open_project_repo_in_browser"
    assert approvals[0]["arguments"] == {"project": "Void", "mode": "visible"}


def test_open_current_project_workspace_endpoint_creates_approval():
    response = request(
        "POST",
        "/projects/current/workspace",
        json={"target": "finder"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "approval" in payload["message"].lower()
    assert payload["result_type"] == "approval"
    assert payload["data"]["action"] == "open_project_workspace"
    assert payload["data"]["arguments"] == {"target": "finder"}


def test_current_workspace_preferences_endpoint_reads_preferences():
    project = _void_project()
    project["workspace"] = {
        "terminal": {"app": "terminal", "command": "cd {root} && nvim ."},
        "browser": {"app": "Safari"},
    }
    _save_projects([project])

    response = request("GET", "/projects/current/workspace/preferences")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["project"]["id"] == "void"
    assert payload["preferences"]["terminal"]["command"] == "cd {root} && nvim ."
    assert "command" in payload["editable_fields"]["terminal"]


def test_update_workspace_preferences_endpoint_creates_approval():
    project = _void_project()
    project["workspace"] = {"browser": {"app": "Default"}}
    _save_projects([project])

    response = request(
        "POST",
        "/projects/current/workspace/preferences",
        json={"section": "browser", "field": "app", "value": "Safari"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["result_type"] == "approval"
    assert payload["data"]["action"] == "update_workspace_preferences"
    assert payload["data"]["arguments"] == {
        "section": "browser",
        "field": "app",
        "value": "Safari",
    }


def test_update_workspace_preferences_endpoint_saves_after_approval():
    project = _void_project()
    project["workspace"] = {"terminal": {"app": "terminal", "command": "cd {root} && nvim ."}}
    _save_projects([project])
    response = request(
        "POST",
        "/projects/current/workspace/preferences",
        json={"section": "terminal", "field": "open_mode", "value": "tab"},
    )
    approval_id = response.json()["data"]["approval_id"]

    approved = request("POST", f"/approvals/{approval_id}/approve")

    assert approved.status_code == 200
    assert approved.json()["ok"] is True
    preferences = request("GET", "/projects/current/workspace/preferences").json()
    assert preferences["preferences"]["terminal"]["open_mode"] == "tab"


def test_run_project_command_endpoint_validates_timeout():
    response = request(
        "POST",
        "/projects/current/commands/test/run",
        json={"timeout_seconds": 0},
    )

    assert response.status_code == 422
    assert response.json()["ok"] is False


def test_tasks():
    response = request("GET", "/tasks")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "tasks": []}


def test_chat_uses_router_without_llm():
    response = request("POST", "/chat", json={"message": "Сделай статистику проекта"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["response"]
    assert "Project statistics" in payload["response"]


def test_chat_returns_clarification_request():
    response = request("POST", "/chat", json={"message": "open project github"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["result_type"] == "clarification_request"
    assert payload["clarification"]["clarification_type"] == "project_selection"
    assert payload["response"] == "Which project do you want to open?"


def test_clarification_endpoints_resume_action():
    request("POST", "/chat", json={"message": "open project github"})

    pending_response = request("GET", "/clarification")
    assert pending_response.status_code == 200
    pending_payload = pending_response.json()
    assert pending_payload["ok"] is True
    assert pending_payload["pending"]["type"] == "project_selection"

    response = request("POST", "/clarification/respond", json={"answer": "Void"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["result_type"] == "tool_call"
    assert "approval" in payload["response"].lower()

    approvals_response = request("GET", "/approvals")
    approvals = approvals_response.json()["pending"]
    assert approvals[0]["action"] == "open_project_repo_in_browser"
    assert approvals[0]["arguments"] == {"project": "Void"}

    cleared_response = request("GET", "/clarification")
    assert cleared_response.json()["pending"] is None


def test_flow_open_project_on_github_clarifies_approves_and_opens_browser(monkeypatch):
    opened: list[tuple[str, str]] = []

    def open_session(url: str, mode: str) -> dict[str, Any]:
        opened.append((url, mode))
        return {
            "session_id": "session_repo",
            "mode": mode,
            "url": url,
            "title": "MihailPy/Void",
            "created_at": "2026-07-03T12:00:00",
            "last_used_at": "2026-07-03T12:00:00",
        }

    monkeypatch.setattr("void.tools.project_tools.browser_sessions.open_session", open_session)

    first = request("POST", "/chat", json={"message": "open project github"})
    assert first.status_code == 200
    assert first.json()["result_type"] == "clarification_request"
    assert first.json()["clarification"]["context"]["available_projects"] == ["Void"]

    second = request("POST", "/clarification/respond", json={"answer": "Void"})
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["result_type"] == "tool_call"
    assert second_payload["data"]["approval_id"]

    assert request("GET", "/clarification").json()["pending"] is None
    approval = _approval_for("open_project_repo_in_browser")
    assert approval["arguments"] == {"project": "Void"}

    approved = request("POST", f"/approvals/{approval['id']}/approve")
    assert approved.status_code == 200
    approved_payload = approved.json()
    assert approved_payload["ok"] is True
    assert approved_payload["result_type"] == "browser_result"
    assert approved_payload["data"]["project"]["name"] == "Void"
    assert approved_payload["data"]["url"] == "https://github.com/MihailPy/Void"
    assert approved_payload["data"]["session_id"] == "session_repo"
    assert approved_payload["data"]["mode"] == "visible"
    assert approved_payload["data"]["title"] == "MihailPy/Void"
    assert opened == [("https://github.com/MihailPy/Void", "visible")]
    assert request("GET", "/approvals").json()["pending"] == []


def test_flow_run_project_command_clarifies_approves_and_executes():
    command = f"{sys.executable} -c \"print('flow ok')\""
    _save_projects([_void_project({"test": command, "verify": command})])

    first = request("POST", "/chat", json={"message": "run project command"})
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["result_type"] == "clarification_request"
    assert "test" in first_payload["clarification"]["context"]["available_commands"]

    second = request("POST", "/clarification/respond", json={"answer": "test"})
    assert second.status_code == 200
    assert second.json()["data"]["action"] == "run_project_command"
    assert request("GET", "/clarification").json()["pending"] is None

    approval = _approval_for("run_project_command")
    assert approval["arguments"]["command_key"] == "test"

    approved = request("POST", f"/approvals/{approval['id']}/approve")
    assert approved.status_code == 200
    approved_payload = approved.json()
    assert approved_payload["ok"] is True
    assert approved_payload["result_type"] == "command_result"
    assert approved_payload["data"]["command_key"] == "test"
    assert approved_payload["data"]["command"] == command
    assert approved_payload["data"]["returncode"] == 0
    assert approved_payload["data"]["stdout"].strip() == "flow ok"
    assert approved_payload["data"]["stderr"] == ""
    assert request("GET", "/approvals").json()["pending"] == []


def test_flow_run_project_command_visible_clarifies_approves_and_launches(monkeypatch):
    command = f"{sys.executable} -c \"print('flow ok')\""
    _save_projects([_void_project({"test": command, "verify": command})])
    launches = []

    def fake_launch(command_text: str, cwd: str) -> dict[str, Any]:
        launches.append((command_text, cwd))
        return {
            "ok": True,
            "terminal_type": "fake-terminal",
            "command": command_text,
            "cwd": cwd,
            "pid": 456,
            "message": "Launched command in fake-terminal.",
        }

    monkeypatch.setattr(
        project_commands.terminal_runner,
        "launch_terminal_command",
        fake_launch,
    )

    first = request("POST", "/chat", json={"message": "run command in terminal"})
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["result_type"] == "clarification_request"
    assert first_payload["clarification"]["context"]["original_action"] == (
        "run_project_command_visible"
    )

    second = request("POST", "/clarification/respond", json={"answer": "test"})
    assert second.status_code == 200
    assert second.json()["data"]["action"] == "run_project_command_visible"

    approval = _approval_for("run_project_command_visible")
    assert approval["arguments"]["command_key"] == "test"

    approved = request("POST", f"/approvals/{approval['id']}/approve")
    assert approved.status_code == 200
    approved_payload = approved.json()
    assert approved_payload["ok"] is True
    assert approved_payload["result_type"] == "terminal_launch_result"
    assert approved_payload["data"]["mode"] == "visible_terminal"
    assert approved_payload["data"]["command_key"] == "test"
    assert approved_payload["data"]["terminal"]["terminal_type"] == "fake-terminal"
    assert approved_payload["data"]["terminal"]["pid"] == 456
    assert launches == [(command, approved_payload["data"]["cwd"])]
    assert request("GET", "/approvals").json()["pending"] == []


def test_flow_switch_project_clarifies_approves_and_updates_context():
    _save_projects(
        [
            _void_project({"test": f"{sys.executable} -c \"print('void')\""}),
            {
                "id": "docs",
                "name": "Docs",
                "aliases": ["documentation"],
                "root_path": ".",
                "repo_url": "https://github.com/MihailPy/Void",
                "commands": {},
            },
        ]
    )

    first = request("POST", "/chat", json={"message": "switch project"})
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["result_type"] == "clarification_request"
    assert first_payload["clarification"]["context"]["available_projects"] == [
        "Docs",
        "Void",
    ]

    second = request("POST", "/clarification/respond", json={"answer": "Docs"})
    assert second.status_code == 200
    assert second.json()["data"]["action"] == "set_current_project"
    assert request("GET", "/clarification").json()["pending"] is None

    approval = _approval_for("set_current_project")
    assert approval["arguments"] == {"project": "Docs"}

    approved = request("POST", f"/approvals/{approval['id']}/approve")
    assert approved.status_code == 200
    approved_payload = approved.json()
    assert approved_payload["ok"] is True
    assert approved_payload["result_type"] == "message"
    assert approved_payload["data"]["project"]["id"] == "docs"
    assert request("GET", "/approvals").json()["pending"] == []

    current = request("GET", "/projects/current")
    assert current.json()["project"]["id"] == "docs"


def test_clarification_respond_without_pending_does_not_call_chat():
    response = request("POST", "/clarification/respond", json={"answer": "Void"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["result_type"] == "final_answer"
    assert payload["response"] == "No pending clarification."


def test_git_status_endpoint():
    response = request("GET", "/git/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert isinstance(payload["message"], str)


def test_git_commit_endpoint_creates_approval():
    response = request("POST", "/git/commit", json={"message": "test"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "approval" in payload["message"].lower()


def test_browser_click_endpoint_creates_approval():
    response = request(
        "POST",
        "/browser/click",
        json={"url": "https://example.com", "selector": "#login"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "approval" in payload["message"].lower()


def test_browser_fill_endpoint_requires_selector():
    response = request(
        "POST",
        "/browser/fill",
        json={"url": "https://example.com", "value": "test@test.com"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False


def test_browser_wait_endpoint_validates_timeout():
    response = request(
        "POST",
        "/browser/wait",
        json={
            "url": "https://example.com",
            "selector": "#result",
            "timeout_ms": 0,
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False


def test_browser_open_session_endpoint_creates_approval():
    response = request(
        "POST",
        "/browser/sessions",
        json={"url": "https://example.com", "mode": "visible"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "approval" in payload["message"].lower()


def test_browser_sessions_endpoint_lists_sessions():
    response = request("GET", "/browser/sessions")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "sessions": []}


def test_browser_open_session_endpoint_rejects_invalid_mode():
    response = request(
        "POST",
        "/browser/sessions",
        json={"url": "https://example.com", "mode": "personal"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False


def test_browser_session_wait_endpoint_validates_timeout():
    response = request(
        "POST",
        "/browser/sessions/abc123/wait",
        json={"selector": "#result", "timeout_ms": 0},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
