"""Small macOS iTerm2 workspace adapter."""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from typing import Any

APP = "iterm2"
MARKER_PREFIX = "void-workspace:"
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
TIMEOUT_SECONDS = 8


def is_supported() -> bool:
    """Return whether iTerm2 AppleScript control is available on this host."""
    return platform.system() == "Darwin" and shutil.which("osascript") is not None


def is_running() -> bool:
    """Return whether iTerm2 is currently running."""
    if platform.system() != "Darwin" or shutil.which("osascript") is None:
        return False
    result = _run_applescript('application "iTerm2" is running')
    return result.get("ok") is True and result.get("stdout", "").strip().lower() == "true"


def open_workspace(
    root_path: str,
    command: str,
    *,
    project_id: str,
    reuse_existing: bool = True,
    open_mode: str = "tab",
    profile: str | None = None,
    window_bounds: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Activate or create one marked iTerm2 workspace for a project."""
    clean_root = str(root_path)
    clean_command = str(command)
    clean_mode = str(open_mode or "tab").strip().casefold()
    if clean_mode not in {"tab", "window"}:
        return _failure(
            clean_root,
            clean_command,
            f"Unsupported iTerm2 open_mode: {open_mode}. Supported values: tab, window.",
        )

    marker_result = _workspace_marker(project_id)
    if not marker_result["ok"]:
        return _failure(clean_root, clean_command, marker_result["message"])
    marker = marker_result["marker"]

    bounds_error = _validate_window_bounds(window_bounds)
    if bounds_error:
        return _failure(clean_root, clean_command, bounds_error)

    if platform.system() != "Darwin":
        return _failure(clean_root, clean_command, "Smart iTerm2 workspaces are supported only on macOS.")
    if shutil.which("osascript") is None:
        return _failure(clean_root, clean_command, "osascript is required for Smart iTerm2 workspaces.")

    running = is_running()
    if reuse_existing and running:
        existing = _activate_existing(marker, window_bounds)
        if not existing.get("ok"):
            return _failure(clean_root, clean_command, str(existing.get("message") or "Failed to inspect iTerm2."))
        if existing.get("found"):
            return {
                "ok": True,
                "app": APP,
                "action": "activated_existing",
                "window_id": existing.get("window_id"),
                "tab_id": existing.get("tab_id"),
                "session_id": existing.get("session_id"),
                "command": clean_command,
                "cwd": clean_root,
                "marker": marker,
                "message": "Activated existing iTerm2 workspace.",
            }

    created = _create_workspace(marker, clean_command, clean_mode, profile, window_bounds)
    if not created.get("ok"):
        return _failure(clean_root, clean_command, str(created.get("message") or "Failed to open iTerm2 workspace."))

    action = str(created.get("action") or ("opened_window" if clean_mode == "window" else "opened_tab"))
    return {
        "ok": True,
        "app": APP,
        "action": action,
        "window_id": created.get("window_id"),
        "tab_id": created.get("tab_id"),
        "session_id": created.get("session_id"),
        "command": clean_command,
        "cwd": clean_root,
        "marker": marker,
        "message": "Opened iTerm2 workspace.",
    }


def _failure(cwd: str, command: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "app": APP,
        "action": "failed",
        "window_id": None,
        "tab_id": None,
        "session_id": None,
        "command": command,
        "cwd": cwd,
        "message": message,
    }


def _workspace_marker(project_id: str) -> dict[str, Any]:
    clean_project_id = str(project_id or "").strip()
    if not PROJECT_ID_RE.fullmatch(clean_project_id):
        return {"ok": False, "message": "Invalid project id for iTerm2 workspace marker."}
    return {"ok": True, "marker": f"{MARKER_PREFIX}{clean_project_id}"}


def _validate_window_bounds(bounds: dict[str, int] | None) -> str | None:
    if bounds is None:
        return None
    required = ("left", "top", "right", "bottom")
    if set(bounds) != set(required):
        return "iTerm2 window_bounds must contain left, top, right, and bottom."
    try:
        left, top, right, bottom = (int(bounds[key]) for key in required)
    except (TypeError, ValueError):
        return "iTerm2 window_bounds values must be integers."
    if left >= right or top >= bottom:
        return "iTerm2 window_bounds must satisfy left < right and top < bottom."
    return None


def _escape_applescript_string(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _run_applescript(script: str) -> dict[str, Any]:
    osascript = shutil.which("osascript")
    if osascript is None:
        return {"ok": False, "stdout": "", "stderr": "osascript is not available."}
    try:
        completed = subprocess.run(
            [osascript],
            input=script,
            text=True,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "iTerm2 AppleScript command timed out."}
    except OSError as error:
        return {"ok": False, "stdout": "", "stderr": f"Failed to run osascript: {error}"}
    return {
        "ok": completed.returncode == 0,
        "stdout": completed.stdout.strip("\r\n"),
        "stderr": completed.stderr.strip(),
        "returncode": completed.returncode,
    }


def _bounds_script(bounds: dict[str, int] | None, window_ref: str = "w") -> str:
    if bounds is None:
        return ""
    left = int(bounds["left"])
    top = int(bounds["top"])
    right = int(bounds["right"])
    bottom = int(bounds["bottom"])
    return f"set bounds of {window_ref} to {{{left}, {top}, {right}, {bottom}}}\n"


def _parse_workspace_response(stdout: str) -> dict[str, Any]:
    parts = str(stdout or "").strip("\r\n").split("\t")
    if len(parts) < 4:
        return {"ok": False, "message": "Unexpected iTerm2 AppleScript response."}
    return {
        "ok": True,
        "action": parts[0],
        "window_id": parts[1],
        "tab_id": parts[2],
        "session_id": parts[3],
        "found": parts[0] == "found",
    }


def _activate_existing(marker: str, bounds: dict[str, int] | None) -> dict[str, Any]:
    marker_literal = _escape_applescript_string(marker)
    bounds_line = _bounds_script(bounds, "w")
    script = f"""
tell application "iTerm2"
    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                if name of s is {marker_literal} then
                    activate
                    select w
                    select t
                    select s
                    {bounds_line}return "found" & tab & (id of w as text) & tab & (index of t as text) & tab & (id of s as text)
                end if
            end repeat
        end repeat
    end repeat
end tell
return "missing" & tab & "" & tab & "" & tab & ""
""".strip()
    result = _run_applescript(script)
    if not result.get("ok"):
        return {"ok": False, "message": result.get("stderr") or "Failed to inspect iTerm2 sessions."}
    parsed = _parse_workspace_response(str(result.get("stdout") or ""))
    if not parsed.get("ok"):
        return parsed
    parsed["ok"] = True
    return parsed


def _profile_clause(profile: str | None) -> str:
    clean_profile = str(profile or "").strip()
    if not clean_profile:
        return "default profile"
    return "profile " + _escape_applescript_string(clean_profile)


def _create_workspace(
    marker: str,
    command: str,
    open_mode: str,
    profile: str | None,
    bounds: dict[str, int] | None,
) -> dict[str, Any]:
    marker_literal = _escape_applescript_string(marker)
    command_literal = _escape_applescript_string(command)
    profile_clause = _profile_clause(profile)
    bounds_line = _bounds_script(bounds, "w")
    desired_mode_literal = _escape_applescript_string(open_mode)
    script = f"""
set desiredMode to {desired_mode_literal}
tell application "iTerm2"
    activate
    if desiredMode is "window" or (count of windows) is 0 then
        set w to (create window with {profile_clause})
        set actionName to "opened_window"
    else
        set w to current window
        tell w to set t to (create tab with {profile_clause})
        set actionName to "opened_tab"
    end if
    if actionName is "opened_window" then
        set t to current tab of w
    end if
    set s to current session of t
    set name of s to {marker_literal}
    {bounds_line}tell s to write text {command_literal}
    return actionName & tab & (id of w as text) & tab & (index of t as text) & tab & (id of s as text)
end tell
""".strip()
    result = _run_applescript(script)
    if not result.get("ok"):
        return {"ok": False, "message": result.get("stderr") or "Failed to create iTerm2 workspace."}
    return _parse_workspace_response(str(result.get("stdout") or ""))
