"""Project inspection and context tools."""

from collections import Counter
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
from typing import Any

from void.core import activity_history
from void.core import browser_sessions
from void.core import project_commands
from void.core import project_context
from void.core import terminal_runner
from void.core import workspace as workspace_core
from void.core.browser_safety import validate_url
from void.core.safety import IGNORED_NAMES, safe_project_path
from void.core.types import ToolDefinition, ToolResult


def _activity_project(project: dict) -> dict:
    return activity_history.compact_project(project)


def _should_skip(path: Path) -> bool:
    return any(part in IGNORED_NAMES for part in path.parts)


def project_stats(path: str = ".") -> ToolResult:
    try:
        root = safe_project_path(path)
    except ValueError as error:
        return ToolResult(ok=False, content=str(error))
    if not root.exists():
        return ToolResult(ok=False, content=f"Path not found: {path}")
    if not root.is_dir():
        return ToolResult(ok=False, content=f"Not a directory: {path}")

    file_count = 0
    folder_count = 0
    extensions: Counter[str] = Counter()

    for item in root.rglob("*"):
        if _should_skip(item.relative_to(root)):
            continue
        if item.is_dir():
            folder_count += 1
        elif item.is_file():
            file_count += 1
            suffix = item.suffix.lower() or "[no extension]"
            extensions[suffix] += 1

    top_level = []
    for item in sorted(root.iterdir(), key=lambda value: (not value.is_dir(), value.name.lower())):
        if item.name in IGNORED_NAMES:
            continue
        prefix = "[DIR]" if item.is_dir() else "[FILE]"
        top_level.append(f"{prefix} {item.name}")

    extension_lines = [
        f"- {extension}: {count}" for extension, count in sorted(extensions.items())
    ]

    content = (
        "Project statistics\n\n"
        f"Files: {file_count}\n"
        f"Folders: {folder_count}\n\n"
        "Files by extension:\n"
        f"{chr(10).join(extension_lines) if extension_lines else '- none'}\n\n"
        "Top-level structure:\n"
        f"{chr(10).join(top_level) if top_level else '- empty'}"
    )

    return ToolResult(
        ok=True,
        content=content,
        data={
            "files": file_count,
            "folders": folder_count,
            "extensions": dict(extensions),
            "top_level": top_level,
        },
    )


def list_projects() -> ToolResult:
    try:
        projects = project_context.list_projects()
    except ValueError as error:
        return ToolResult(ok=False, content=str(error))

    lines = ["Known projects", ""]
    for project in projects:
        aliases = ", ".join(project.get("aliases", [])) or "none"
        lines.append(
            f"- {project['name']} ({project['id']}) "
            f"root={project.get('root_path', '.')} aliases={aliases}"
        )

    return ToolResult(ok=True, content="\n".join(lines), data={"projects": projects})


def get_current_project() -> ToolResult:
    try:
        project = project_context.get_current_project()
    except ValueError as error:
        return ToolResult(ok=False, content=str(error))

    return ToolResult(
        ok=True,
        content=f"Current project: {project['name']} ({project['id']})",
        data={"project": project},
    )


def set_current_project(project: str) -> ToolResult:
    result = project_context.set_current_project(project)
    if not result["ok"]:
        activity_history.log_activity(
            "project_switch",
            "failure",
            f"Failed to switch project to {project}",
            {
                "project": project,
                "replay": {
                    "action": "set_current_project",
                    "arguments": {"project": project},
                },
            },
        )
        return ToolResult(ok=False, content=result["error"])

    selected = result["project"]
    activity_history.log_activity(
        "project_switch",
        "success",
        f"Switched project to {selected['name']}",
        {
            "project": _activity_project(selected),
            "replay": {
                "action": "set_current_project",
                "arguments": {"project": selected["id"]},
            },
        },
    )
    return ToolResult(
        ok=True,
        content=f"Current project set to {selected['name']} ({selected['id']}).",
        data={"project": selected},
    )


def open_project_repo(project: str) -> ToolResult:
    selected = project_context.find_project(project)
    if selected is None:
        activity_history.log_activity(
            "repo_open",
            "failure",
            f"Failed to resolve project repo for {project}",
            {
                "project": project,
                "replay": {
                    "action": "open_project_repo",
                    "arguments": {"project": project},
                },
            },
        )
        return ToolResult(ok=False, content=f"Project not found: {project}")

    repo_url = str(selected.get("repo_url") or "").strip()
    if not repo_url:
        activity_history.log_activity(
            "repo_open",
            "failure",
            f"Project has no repo_url configured: {selected['name']}",
            {
                "project": _activity_project(selected),
                "replay": {
                    "action": "open_project_repo",
                    "arguments": {"project": selected["id"]},
                },
            },
        )
        return ToolResult(
            ok=False,
            content=f"Project has no repo_url configured: {selected['name']}",
            data={"project": selected},
        )

    activity_history.log_activity(
        "repo_open",
        "success",
        f"Resolved repository for {selected['name']}",
        {
            "project": _activity_project(selected),
            "url": repo_url,
            "replay": {
                "action": "open_project_repo",
                "arguments": {"project": selected["id"]},
            },
        },
    )
    return ToolResult(
        ok=True,
        content=f"Project GitHub repository for {selected['name']}: {repo_url}",
        data={"project": selected, "url": repo_url},
    )


def _find_project_or_current(project: str) -> dict | None:
    if project.strip().casefold() in {"current", "current project", "текущий", "текущий проект"}:
        try:
            return project_context.get_current_project()
        except ValueError:
            return None
    return project_context.find_project(project)


def _optional_project_or_current(project: str | None) -> dict | None:
    if project is None or not str(project).strip():
        try:
            return project_context.get_current_project()
        except ValueError:
            return None
    return _find_project_or_current(str(project))


def _log_workspace_open(
    selected: dict[str, Any] | str,
    target: str,
    status: str,
    summary: str,
    project_arg: str | None,
) -> None:
    metadata_project: Any = (
        _activity_project(selected) if isinstance(selected, dict) else selected
    )
    activity_history.log_activity(
        "workspace_open",
        status,
        summary,
        {
            "project": metadata_project,
            "target": target,
            "status": status,
            "replay": {
                "action": "open_project_workspace",
                "arguments": {
                    "project": selected["id"] if isinstance(selected, dict) else project_arg,
                    "target": target,
                },
            },
        },
    )


def _launch_file_manager(root: str) -> dict[str, Any]:
    system = platform.system()
    try:
        if system == "Darwin":
            if shutil.which("open") is None:
                return {"ok": False, "target": root, "message": "open is not available."}
            process = subprocess.Popen(
                ["open", root],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"ok": True, "target": root, "launcher": "open", "pid": process.pid}
        if system == "Windows":
            process = subprocess.Popen(
                ["explorer", root],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"ok": True, "target": root, "launcher": "explorer", "pid": process.pid}
        if system == "Linux":
            if shutil.which("xdg-open") is None:
                return {"ok": False, "target": root, "message": "xdg-open is not available."}
            process = subprocess.Popen(
                ["xdg-open", root],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"ok": True, "target": root, "launcher": "xdg-open", "pid": process.pid}
        return {
            "ok": False,
            "target": root,
            "message": f"File manager launch is not supported on {system}.",
        }
    except OSError as error:
        return {"ok": False, "target": root, "message": f"Failed to open file manager: {error}"}


def _open_url_with_app(url: str, app: str) -> dict[str, Any]:
    system = platform.system()
    clean_app = app.strip()
    try:
        if system == "Darwin":
            if shutil.which("open") is None:
                return {"ok": False, "url": url, "message": "open is not available."}
            args = ["open", "-a", clean_app, url] if clean_app else ["open", url]
            process = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"ok": True, "url": url, "browser_app": clean_app, "pid": process.pid}
        return {
            "ok": False,
            "url": url,
            "message": "Preferred browser app launch is only supported on macOS.",
        }
    except OSError as error:
        return {"ok": False, "url": url, "message": f"Failed to open browser app: {error}"}


def _open_workspace_url(url: str, config: dict[str, str]) -> tuple[bool, list[str], dict[str, Any]]:
    normalized_url = validate_url(url)
    app = str(config.get("app") or "").strip()
    if app and app.casefold() not in {"default", "managed", "browser"}:
        opened = _open_url_with_app(normalized_url, app)
        lines = [
            "Opened project URL in configured browser.",
            f"Repo URL: {normalized_url}",
            f"Browser app: {app}",
            f"Status: {opened.get('message', 'launched')}",
        ]
        return bool(opened.get("ok")), lines, {"url": normalized_url, "browser": opened}

    session = browser_sessions.open_session(normalized_url, "visible")
    lines = [
        "Opened project URL in browser.",
        f"Repo URL: {session.get('url', normalized_url)}",
        f"Mode: {session.get('mode', 'visible')}",
        f"Session ID: {session.get('session_id', '')}",
    ]
    title = session.get("title")
    if title:
        lines.append(f"Title: {title}")
    return True, lines, {
        "url": session.get("url", normalized_url),
        "mode": session.get("mode", "visible"),
        "session_id": session.get("session_id"),
        "title": title,
        "session": session,
    }


def open_project_repo_in_browser(project: str, mode: str = "visible") -> ToolResult:
    selected = _find_project_or_current(project)
    if selected is None:
        activity_history.log_activity(
            "repo_open",
            "failure",
            f"Failed to open project repo for {project}",
            {
                "project": project,
                "mode": mode,
                "replay": {
                    "action": "open_project_repo_in_browser",
                    "arguments": {"project": project, "mode": mode},
                },
            },
        )
        return ToolResult(ok=False, content=f"Project not found: {project}")

    repo_url = str(selected.get("repo_url") or "").strip()
    if not repo_url:
        activity_history.log_activity(
            "repo_open",
            "failure",
            f"Project has no repo_url configured: {selected['name']}",
            {
                "project": _activity_project(selected),
                "mode": mode,
                "replay": {
                    "action": "open_project_repo_in_browser",
                    "arguments": {"project": selected["id"], "mode": mode},
                },
            },
        )
        return ToolResult(
            ok=False,
            content=f"Project has no repo_url configured: {selected['name']}",
            data={"project": selected},
        )

    clean_mode = mode.strip().casefold()
    if clean_mode not in {"visible", "headless"}:
        activity_history.log_activity(
            "repo_open",
            "failure",
            f"Invalid browser mode for project repo: {mode}",
            {
                "project": _activity_project(selected),
                "mode": mode,
                "replay": {
                    "action": "open_project_repo_in_browser",
                    "arguments": {"project": selected["id"], "mode": mode},
                },
            },
        )
        return ToolResult(ok=False, content="Mode must be one of: visible, headless.")

    try:
        normalized_url = validate_url(repo_url)
        session = browser_sessions.open_session(normalized_url, clean_mode)
    except ValueError as error:
        activity_history.log_activity(
            "repo_open",
            "failure",
            f"Failed to open repository for {selected['name']}",
            {
                "project": _activity_project(selected),
                "url": repo_url,
                "mode": clean_mode,
                "replay": {
                    "action": "open_project_repo_in_browser",
                    "arguments": {"project": selected["id"], "mode": clean_mode},
                },
            },
        )
        return ToolResult(
            ok=False,
            content=f"Invalid repo_url for {selected['name']}: {error}",
            data={"project": selected, "url": repo_url},
        )

    title = session.get("title")
    lines = [
        "Opened project repository in browser.",
        f"Project: {selected['name']} ({selected['id']})",
        f"Repo URL: {session.get('url', normalized_url)}",
        f"Mode: {session.get('mode', clean_mode)}",
        f"Session ID: {session.get('session_id', '')}",
    ]
    if title:
        lines.append(f"Title: {title}")

    activity_history.log_activity(
        "repo_open",
        "success",
        f"Opened repository for {selected['name']} in browser",
        {
            "project": _activity_project(selected),
            "url": session.get("url", normalized_url),
            "mode": session.get("mode", clean_mode),
            "session_id": session.get("session_id"),
            "replay": {
                "action": "open_project_repo_in_browser",
                "arguments": {"project": selected["id"], "mode": clean_mode},
            },
        },
    )
    activity_history.log_activity(
        "browser_session_open",
        "success",
        f"Opened {session.get('mode', clean_mode)} browser session",
        {
            "project": _activity_project(selected),
            "url": session.get("url", normalized_url),
            "mode": session.get("mode", clean_mode),
            "session_id": session.get("session_id"),
            "replay": {
                "action": "open_project_repo_in_browser",
                "arguments": {"project": selected["id"], "mode": clean_mode},
            },
        },
    )
    return ToolResult(
        ok=True,
        content="\n".join(lines),
        data={
            "project": selected,
            "url": session.get("url", normalized_url),
            "mode": session.get("mode", clean_mode),
            "session_id": session.get("session_id"),
            "title": title,
            "session": session,
        },
    )


def open_project_workspace(project: str | None = None, target: str | None = None) -> ToolResult:
    clean_target = (target or "terminal").strip().casefold()
    selected = _optional_project_or_current(project)
    if selected is None:
        project_label = project or "current project"
        _log_workspace_open(
            project_label,
            clean_target or "terminal",
            "failure",
            "Project not found",
            project,
        )
        return ToolResult(ok=False, content=f"Project not found: {project_label}")

    try:
        resolved = workspace_core.resolve_workspace_target(selected, target)
    except ValueError as error:
        _log_workspace_open(
            selected,
            clean_target or "terminal",
            "failure",
            f"Failed to resolve workspace for {selected['name']}",
            project,
        )
        return ToolResult(ok=False, content=str(error), data={"project": selected})

    target_name = resolved["target"]
    config = resolved["config"]
    root = resolved["root"]

    try:
        if target_name == "editor":
            _log_workspace_open(
                selected,
                target_name,
                "failure",
                f"Editor workspace is not implemented for {selected['name']}",
                project,
            )
            return ToolResult(
                ok=False,
                content="Editor workspace is not implemented yet.",
                data={"project": selected, "target": target_name},
            )

        if target_name == "terminal":
            command = str(config.get("command") or "").strip()
            if not command:
                _log_workspace_open(
                    selected,
                    target_name,
                    "failure",
                    f"Workspace terminal command is not configured for {selected['name']}",
                    project,
                )
                return ToolResult(
                    ok=False,
                    content=f"Workspace terminal command is not configured for {selected['name']}.",
                    data={"project": selected, "target": target_name, "cwd": root},
                )

            command = command.replace("{root}", shlex.quote(root))
            terminal = terminal_runner.launch_terminal_command(command, root)
            status = "success" if terminal.get("ok") else "failure"
            lines = [
                "Project workspace terminal launch"
                if terminal.get("ok")
                else "Project workspace terminal launch failed",
                f"Project: {selected['name']} ({selected['id']})",
                f"Target: {target_name}",
                f"Command: {command}",
                f"CWD: {root}",
                f"Terminal: {terminal.get('terminal_type', 'unknown')}",
                f"Status: {terminal.get('message', '')}",
            ]
            if terminal.get("pid") is not None:
                lines.append(f"PID: {terminal['pid']}")
            _log_workspace_open(
                selected,
                target_name,
                status,
                f"Opened {target_name} workspace for {selected['name']}",
                project,
            )
            return ToolResult(
                ok=bool(terminal.get("ok")),
                content="\n".join(lines),
                data={
                    "project": selected,
                    "target": target_name,
                    "command": command,
                    "cwd": root,
                    "mode": "visible_terminal",
                    "terminal": terminal,
                },
            )

        if target_name == "finder":
            opened = _launch_file_manager(root)
            status = "success" if opened.get("ok") else "failure"
            _log_workspace_open(
                selected,
                target_name,
                status,
                f"Opened {target_name} workspace for {selected['name']}",
                project,
            )
            return ToolResult(
                ok=bool(opened.get("ok")),
                content=(
                    f"Opened project in file manager: {root}"
                    if opened.get("ok")
                    else str(opened.get("message", "Failed to open file manager."))
                ),
                data={
                    "project": selected,
                    "target": target_name,
                    "cwd": root,
                    "file_manager": opened,
                },
            )

        if target_name in {"github", "browser"}:
            repo_url = str(selected.get("repo_url") or "").strip()
            if not repo_url:
                _log_workspace_open(
                    selected,
                    target_name,
                    "failure",
                    f"Project has no repo_url configured: {selected['name']}",
                    project,
                )
                return ToolResult(
                    ok=False,
                    content=f"Project has no repo_url configured: {selected['name']}",
                    data={"project": selected, "target": target_name},
                )
            ok, lines, data = _open_workspace_url(repo_url, config if target_name == "browser" else {})
            _log_workspace_open(
                selected,
                target_name,
                "success" if ok else "failure",
                f"Opened {target_name} workspace for {selected['name']}",
                project,
            )
            return ToolResult(
                ok=ok,
                content="\n".join(
                    [
                        f"Project: {selected['name']} ({selected['id']})",
                        f"Target: {target_name}",
                        *lines,
                    ]
                ),
                data={"project": selected, "target": target_name, **data},
            )
    except ValueError as error:
        _log_workspace_open(
            selected,
            target_name,
            "failure",
            f"Failed to open {target_name} workspace for {selected['name']}",
            project,
        )
        return ToolResult(
            ok=False,
            content=str(error),
            data={"project": selected, "target": target_name},
        )

    return ToolResult(ok=False, content=f"Unsupported workspace target: {target_name}")


def describe_current_project() -> ToolResult:
    try:
        project = project_context.get_current_project()
        description = project_context.describe_current_project()
    except ValueError as error:
        return ToolResult(ok=False, content=str(error))

    return ToolResult(ok=True, content=description, data={"project": project})


def list_project_commands() -> ToolResult:
    try:
        payload = project_commands.list_project_commands()
    except ValueError as error:
        return ToolResult(ok=False, content=str(error))

    commands = payload["commands"]
    lines = [
        f"Project commands for {payload['project']['name']} ({payload['project']['id']})",
        f"CWD: {payload['cwd']}",
        "",
    ]
    if commands:
        lines.extend(f"- {key}: {command}" for key, command in commands.items())
    else:
        lines.append("- none configured")

    return ToolResult(ok=True, content="\n".join(lines), data=payload)


def get_project_command(command_key: str) -> ToolResult:
    try:
        payload = project_commands.get_project_command(command_key)
    except ValueError as error:
        return ToolResult(ok=False, content=str(error))

    return ToolResult(
        ok=True,
        content=f"{payload['key']}: {payload['command']}",
        data=payload,
    )


def run_project_command(command_key: str, timeout_seconds: int = 120) -> ToolResult:
    try:
        payload = project_commands.run_project_command(command_key, timeout_seconds)
    except ValueError as error:
        activity_history.log_activity(
            "project_command",
            "failure",
            f"Failed to run project command {command_key}",
            {"command_key": command_key},
        )
        return ToolResult(ok=False, content=str(error), data={"command_key": command_key})

    project = payload["project"]
    status = "timed out" if payload["timed_out"] else "completed"
    lines = [
        f"Project command {status}: {payload['command_key']}",
        f"Project: {project['name']} ({project['id']})",
        f"Command: {payload['command']}",
        f"CWD: {payload['cwd']}",
        f"Return code: {payload['returncode']}",
        f"Duration: {payload['duration_seconds']}s",
    ]
    if payload.get("error"):
        lines.extend(["", payload["error"]])
    lines.extend(
        [
            "",
            "stdout:",
            payload["stdout"] or "(empty)",
            "",
            "stderr:",
            payload["stderr"] or "(empty)",
        ]
    )

    activity_history.log_activity(
        "project_command",
        "success" if payload["ok"] else "failure",
        f"Ran {payload['command_key']} for {project['name']}",
        {
            "project": _activity_project(project),
            "command_key": payload["command_key"],
            "timeout_seconds": timeout_seconds,
            "cwd": payload["cwd"],
            "returncode": payload["returncode"],
            "replay": {
                "action": "run_project_command",
                "arguments": {
                    "command_key": payload["command_key"],
                    "timeout_seconds": timeout_seconds,
                },
            },
        },
    )
    return ToolResult(ok=payload["ok"], content="\n".join(lines), data=payload)


def run_project_command_visible(command_key: str) -> ToolResult:
    try:
        payload = project_commands.run_project_command_visible(command_key)
    except ValueError as error:
        activity_history.log_activity(
            "terminal",
            "failure",
            f"Failed to launch project command {command_key} in terminal",
            {"command_key": command_key},
        )
        return ToolResult(ok=False, content=str(error), data={"command_key": command_key})

    project = payload["project"]
    terminal = payload["terminal"]
    status = "launched" if payload["ok"] else "failed to launch"
    lines = [
        f"Project command {status} in visible terminal: {payload['command_key']}",
        f"Project: {project['name']} ({project['id']})",
        f"Command: {payload['command']}",
        f"CWD: {payload['cwd']}",
        f"Terminal: {terminal.get('terminal_type', 'unknown')}",
        f"Status: {terminal.get('message', '')}",
    ]
    if terminal.get("pid") is not None:
        lines.append(f"PID: {terminal['pid']}")

    activity_history.log_activity(
        "terminal",
        "success" if payload["ok"] else "failure",
        f"Launched {payload['command_key']} in visible terminal"
        if payload["ok"]
        else f"Failed to launch {payload['command_key']} in visible terminal",
        {
            "project": _activity_project(project),
            "command_key": payload["command_key"],
            "cwd": payload["cwd"],
            "terminal_type": terminal.get("terminal_type"),
            "replay": {
                "action": "run_project_command_visible",
                "arguments": {"command_key": payload["command_key"]},
            },
        },
    )
    return ToolResult(ok=payload["ok"], content="\n".join(lines), data=payload)


def definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            "project_stats",
            "Summarize project files and folders.",
            project_stats,
            category="filesystem",
            risk_level="read",
        ),
        ToolDefinition(
            "list_projects",
            "List known project contexts.",
            list_projects,
            category="project",
            risk_level="read",
        ),
        ToolDefinition(
            "get_current_project",
            "Show the current project context.",
            get_current_project,
            category="project",
            risk_level="read",
        ),
        ToolDefinition(
            "set_current_project",
            "Set the current project context by id, name, or alias.",
            set_current_project,
            requires_confirmation=True,
            category="project",
            risk_level="write",
        ),
        ToolDefinition(
            "open_project_repo",
            "Return the configured GitHub repository URL for a known project.",
            open_project_repo,
            category="project",
            risk_level="read",
        ),
        ToolDefinition(
            "open_project_repo_in_browser",
            "Open the configured project repository URL in a managed browser session.",
            open_project_repo_in_browser,
            requires_confirmation=True,
            category="project",
            risk_level="network",
        ),
        ToolDefinition(
            "open_project_workspace",
            "Open a configured project workspace target.",
            open_project_workspace,
            requires_confirmation=True,
            category="project",
            risk_level="write",
        ),
        ToolDefinition(
            "describe_current_project",
            "Describe the current project context.",
            describe_current_project,
            category="project",
            risk_level="read",
        ),
        ToolDefinition(
            "list_project_commands",
            "List predefined commands for the current project.",
            list_project_commands,
            category="project",
            risk_level="read",
        ),
        ToolDefinition(
            "run_project_command",
            "Run a predefined command for the current project.",
            run_project_command,
            requires_confirmation=True,
            category="project",
            risk_level="write",
        ),
        ToolDefinition(
            "run_project_command_visible",
            "Run a predefined command for the current project in a visible terminal.",
            run_project_command_visible,
            requires_confirmation=True,
            category="project",
            risk_level="write",
        ),
    ]
