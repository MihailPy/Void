"""Launch predefined commands in a visible system terminal."""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _shell_command(command: str, cwd: str) -> str:
    quoted_cwd = shlex.quote(str(Path(cwd)))
    return (
        f"cd {quoted_cwd} && ({command}); "
        "status=$?; echo; "
        "echo \"[Void] Command finished with exit code $status. "
        "This terminal will remain open.\"; "
        "exec ${SHELL:-/bin/sh} -l"
    )


def _applescript_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _popen_result(
    process: subprocess.Popen[Any],
    terminal_type: str,
    command: str,
    cwd: str,
) -> dict[str, Any]:
    return {
        "ok": True,
        "terminal_type": terminal_type,
        "command": command,
        "cwd": cwd,
        "pid": process.pid,
        "message": f"Launched command in {terminal_type}.",
    }


def terminal_supported() -> bool:
    """Return whether a visible terminal launch is supported on this host."""
    system = platform.system()
    if system == "Darwin":
        return shutil.which("osascript") is not None
    if system == "Linux":
        return any(
            shutil.which(name) is not None
            for name in ("gnome-terminal", "xterm", "konsole")
        )
    if system == "Windows":
        return shutil.which("cmd.exe") is not None or bool(os.environ.get("COMSPEC"))
    return False


def launch_terminal_command(command: str, cwd: str) -> dict[str, Any]:
    """Open a visible terminal window and run command without capturing output."""
    clean_command = command.strip()
    clean_cwd = str(Path(cwd))
    if not clean_command:
        return {
            "ok": False,
            "terminal_type": "unsupported",
            "command": command,
            "cwd": clean_cwd,
            "pid": None,
            "message": "Command is required.",
        }

    system = platform.system()
    wrapped = _shell_command(clean_command, clean_cwd)

    try:
        if system == "Darwin":
            if shutil.which("osascript") is None:
                return {
                    "ok": False,
                    "terminal_type": "macos_terminal",
                    "command": clean_command,
                    "cwd": clean_cwd,
                    "pid": None,
                    "message": "osascript is required to open Terminal.app.",
                }
            escaped = _applescript_escape(wrapped)
            process = subprocess.Popen(
                [
                    "osascript",
                    "-e",
                    f'tell application "Terminal" to do script "{escaped}"',
                    "-e",
                    'tell application "Terminal" to activate',
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return _popen_result(process, "macos_terminal", clean_command, clean_cwd)

        if system == "Linux":
            for terminal_type, args in (
                (
                    "gnome-terminal",
                    ["gnome-terminal", "--", "bash", "-lc", wrapped],
                ),
                ("xterm", ["xterm", "-hold", "-e", "sh", "-lc", wrapped]),
                ("konsole", ["konsole", "--hold", "-e", "sh", "-lc", wrapped]),
            ):
                if shutil.which(args[0]) is None:
                    continue
                process = subprocess.Popen(
                    args,
                    cwd=clean_cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return _popen_result(process, terminal_type, clean_command, clean_cwd)
            return {
                "ok": False,
                "terminal_type": "unsupported",
                "command": clean_command,
                "cwd": clean_cwd,
                "pid": None,
                "message": "No supported terminal emulator found.",
            }

        if system == "Windows":
            comspec = os.environ.get("COMSPEC") or shutil.which("cmd.exe")
            if not comspec:
                return {
                    "ok": False,
                    "terminal_type": "windows_cmd",
                    "command": clean_command,
                    "cwd": clean_cwd,
                    "pid": None,
                    "message": "cmd.exe is required to open a visible terminal.",
                }
            windows_cwd = clean_cwd.replace('"', '""')
            process = subprocess.Popen(
                [
                    comspec,
                    "/c",
                    "start",
                    "cmd.exe",
                    "/k",
                    f'cd /d "{windows_cwd}" && {clean_command}',
                ],
                cwd=clean_cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return _popen_result(process, "windows_cmd", clean_command, clean_cwd)

        return {
            "ok": False,
            "terminal_type": "unsupported",
            "command": clean_command,
            "cwd": clean_cwd,
            "pid": None,
            "message": f"Visible terminal launch is not supported on {system}.",
        }
    except OSError as error:
        return {
            "ok": False,
            "terminal_type": system.lower() or "unsupported",
            "command": clean_command,
            "cwd": clean_cwd,
            "pid": None,
            "message": f"Failed to launch terminal: {error}",
        }
