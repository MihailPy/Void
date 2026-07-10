from __future__ import annotations

from typing import Any

from void.core import activity_history, project_context, workspace
from void.core.permissions import approve, clear_approval, list_approvals
from void.core.router import Router
from void.core.types import AgentAction
from void.tools.builtin import build_registry


def _save_workspace(
    workspace_config: dict[str, dict[str, str]] | None = None,
    repo_url: str = "https://github.com/MihailPy/Void",
) -> None:
    project: dict[str, Any] = {
        "id": "void",
        "name": "Void",
        "aliases": ["void", "MihailPy/Void"],
        "root_path": ".",
        "repo_url": repo_url,
        "commands": {},
    }
    if workspace_config is not None:
        project["workspace"] = workspace_config
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


def test_workspace_parsing_preserves_optional_config():
    _save_workspace(
        {
            "terminal": {"app": "iterm2", "command": "cd {root} && nvim ."},
            "file_manager": {"app": "Finder"},
            "browser": {"app": "Safari"},
        }
    )

    project = project_context.get_current_project()

    assert project["workspace"]["terminal"]["command"] == "cd {root} && nvim ."
    assert project["workspace"]["file_manager"]["app"] == "Finder"


def test_missing_workspace_is_empty_and_default_target_is_terminal():
    _save_workspace(None)
    project = project_context.get_current_project()

    assert workspace.get_workspace(project) == {}
    resolved = workspace.resolve_workspace_target(project, None)
    assert resolved["target"] == "terminal"
    assert resolved["config"] == {}
    assert resolved["root"].endswith("Void")


def test_finder_target_resolves_file_manager_config():
    _save_workspace({"file_manager": {"app": "Finder"}})
    project = project_context.get_current_project()

    resolved = workspace.resolve_workspace_target(project, "finder")

    assert resolved["target"] == "finder"
    assert resolved["config"] == {"app": "Finder"}


def test_open_workspace_terminal_uses_configured_command(monkeypatch):
    _save_workspace({"terminal": {"command": "cd {root} && nvim ."}})
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

    monkeypatch.setattr("void.tools.project_tools.terminal_runner.launch_terminal_command", fake_launch)
    registry = build_registry()

    request = registry.execute(AgentAction("open_project_workspace", {}, "test"))
    assert request.ok is True
    assert list_approvals()[0]["action"] == "open_project_workspace"

    result = _approve_latest(registry)

    assert result.ok is True
    assert result.data["target"] == "terminal"
    assert "nvim ." in launches[0][0]
    latest = activity_history.get_last_activity()
    assert latest["activity_type"] == "workspace_open"
    assert latest["metadata"]["project"] == {"id": "void", "name": "Void"}
    assert latest["metadata"]["target"] == "terminal"
    assert latest["metadata"]["status"] == "success"


def test_open_workspace_finder_uses_platform_file_manager(monkeypatch):
    _save_workspace({"file_manager": {"app": "Finder"}})
    monkeypatch.setattr("void.tools.project_tools.platform.system", lambda: "Darwin")
    monkeypatch.setattr("void.tools.project_tools.shutil.which", lambda name: "/usr/bin/open")
    calls: list[list[str]] = []

    class FakeProcess:
        pid = 456

    def fake_popen(args, **kwargs):
        calls.append(args)
        return FakeProcess()

    monkeypatch.setattr("void.tools.project_tools.subprocess.Popen", fake_popen)
    registry = build_registry()

    registry.execute(
        AgentAction("open_project_workspace", {"target": "finder"}, "test")
    )
    result = _approve_latest(registry)

    assert result.ok is True
    assert result.data["target"] == "finder"
    assert calls[0][0] == "open"
    assert activity_history.get_last_activity()["metadata"]["target"] == "finder"


def test_open_workspace_github_opens_repo_with_managed_browser_for_default(monkeypatch):
    _save_workspace({"browser": {"app": "default"}})
    opened: list[tuple[str, str]] = []

    def fake_open_session(url: str, mode: str) -> dict[str, Any]:
        opened.append((url, mode))
        return {
            "session_id": "repo-session",
            "mode": mode,
            "url": url,
            "title": "Repo",
        }

    monkeypatch.setattr("void.tools.project_tools.browser_sessions.open_session", fake_open_session)
    registry = build_registry()

    registry.execute(
        AgentAction("open_project_workspace", {"target": "github"}, "test")
    )
    result = _approve_latest(registry)

    assert result.ok is True
    assert result.data["target"] == "github"
    assert result.data["session_id"] == "repo-session"
    assert opened == [("https://github.com/MihailPy/Void", "visible")]
    assert activity_history.get_last_activity()["activity_type"] == "workspace_open"


def test_open_workspace_github_opens_repo_with_managed_browser_for_managed(monkeypatch):
    _save_workspace({"browser": {"app": "managed"}})
    opened: list[tuple[str, str]] = []

    def fake_open_session(url: str, mode: str) -> dict[str, Any]:
        opened.append((url, mode))
        return {
            "session_id": "repo-session",
            "mode": mode,
            "url": url,
            "title": "Repo",
        }

    monkeypatch.setattr("void.tools.project_tools.browser_sessions.open_session", fake_open_session)
    registry = build_registry()

    registry.execute(
        AgentAction("open_project_workspace", {"target": "github"}, "test")
    )
    result = _approve_latest(registry)

    assert result.ok is True
    assert result.data["target"] == "github"
    assert result.data["session_id"] == "repo-session"
    assert opened == [("https://github.com/MihailPy/Void", "visible")]


def test_open_workspace_github_uses_configured_browser_app(monkeypatch):
    _save_workspace({"browser": {"app": "Safari"}})
    monkeypatch.setattr("void.tools.project_tools.platform.system", lambda: "Darwin")
    monkeypatch.setattr("void.tools.project_tools.shutil.which", lambda name: "/usr/bin/open")
    calls: list[list[str]] = []

    class FakeProcess:
        pid = 789

    def fake_popen(args, **kwargs):
        calls.append(args)
        return FakeProcess()

    monkeypatch.setattr("void.tools.project_tools.subprocess.Popen", fake_popen)
    registry = build_registry()

    registry.execute(
        AgentAction("open_project_workspace", {"target": "github"}, "test")
    )
    result = _approve_latest(registry)

    assert result.ok is True
    assert result.data["target"] == "github"
    assert result.data["browser"]["browser_app"] == "Safari"
    assert calls == [["open", "-a", "Safari", "https://github.com/MihailPy/Void"]]


def test_open_workspace_editor_is_reserved():
    _save_workspace({})
    registry = build_registry()

    registry.execute(
        AgentAction("open_project_workspace", {"target": "editor"}, "test")
    )
    result = _approve_latest(registry)

    assert result.ok is False
    assert result.content == "Editor workspace is not implemented yet."


def test_workspace_replay_requires_approval(monkeypatch):
    _save_workspace({"terminal": {"command": "python -V"}})

    def fake_launch(command: str, cwd: str) -> dict[str, Any]:
        return {
            "ok": True,
            "terminal_type": "fake-terminal",
            "command": command,
            "cwd": cwd,
            "pid": 123,
            "message": "Launched.",
        }

    monkeypatch.setattr("void.tools.project_tools.terminal_runner.launch_terminal_command", fake_launch)
    registry = build_registry()
    activity_history.log_activity(
        "workspace_open",
        "success",
        "Opened terminal workspace for Void",
        {"project": {"id": "void", "name": "Void"}, "target": "terminal"},
    )

    replay_request = registry.execute(AgentAction("repeat_last_activity", {}, "test"))

    assert replay_request.ok is True
    assert list_approvals()[0]["action"] == "open_project_workspace"
    assert list_approvals()[0]["arguments"] == {"project": "void", "target": "terminal"}

    replay_result = _approve_latest(registry)
    assert replay_result.ok is True


def test_router_workspace_phrases():
    cases = {
        "open workspace": {"target": "terminal"},
        "open project": {"target": "terminal"},
        "open project workspace": {"target": "terminal"},
        "open project in finder": {"target": "finder"},
        "open project in browser": {"target": "browser"},
        "открой проект": {"target": "terminal"},
        "открой рабочее пространство": {"target": "terminal"},
        "открой проект в Finder": {"target": "finder"},
    }

    for phrase, arguments in cases.items():
        route = Router().route(phrase)
        assert route.matched is True
        assert route.action is not None
        assert route.action.action == "open_project_workspace"
        assert route.action.arguments == arguments


def test_router_open_project_on_github_requests_clarification():
    route = Router().route("Open project on GitHub")

    assert route.matched is True
    assert route.action is None
    assert route.clarification is not None
    assert route.clarification.clarification_type == "project_selection"


def test_router_open_current_project_on_github_uses_current_project():
    route = Router().route("Open current project on GitHub")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "open_project_workspace"
    assert route.action.arguments == {"target": "github"}
