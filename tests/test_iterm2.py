from __future__ import annotations

import subprocess
from typing import Any

from void.integrations import iterm2


class FakeCompleted:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _macos(monkeypatch):
    monkeypatch.setattr(iterm2.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(iterm2.shutil, "which", lambda name: "/usr/bin/osascript")


def test_non_macos_returns_unsupported(monkeypatch):
    monkeypatch.setattr(iterm2.platform, "system", lambda: "Linux")
    monkeypatch.setattr(iterm2.shutil, "which", lambda name: "/usr/bin/osascript")

    result = iterm2.open_workspace("/tmp/project", "nvim .", project_id="void")

    assert iterm2.is_supported() is False
    assert result["ok"] is False
    assert result["action"] == "failed"
    assert "macOS" in result["message"]


def test_missing_osascript_returns_clear_error(monkeypatch):
    monkeypatch.setattr(iterm2.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(iterm2.shutil, "which", lambda name: None)

    result = iterm2.open_workspace("/tmp/project", "nvim .", project_id="void")

    assert result["ok"] is False
    assert result["action"] == "failed"
    assert "osascript" in result["message"]


def test_existing_exact_marker_produces_activated_existing(monkeypatch):
    _macos(monkeypatch)
    scripts: list[str] = []

    def fake_run(args: list[str], **kwargs: Any) -> FakeCompleted:
        scripts.append(kwargs["input"])
        if len(scripts) == 1:
            return FakeCompleted("true")
        return FakeCompleted("found\t101\t202\t303")

    monkeypatch.setattr(iterm2.subprocess, "run", fake_run)

    result = iterm2.open_workspace("/tmp/project", "cd /tmp/project && nvim .", project_id="void")

    assert result["ok"] is True
    assert result["action"] == "activated_existing"
    assert result["session_id"] == "303"
    assert 'application "iTerm2" is running' in scripts[0]
    assert 'name of s is "void-workspace:void"' in scripts[1]
    assert "write text" not in scripts[1]


def test_missing_marker_creates_tab(monkeypatch):
    _macos(monkeypatch)
    scripts: list[str] = []

    def fake_run(args: list[str], **kwargs: Any) -> FakeCompleted:
        scripts.append(kwargs["input"])
        if len(scripts) == 1:
            return FakeCompleted("true")
        if len(scripts) == 2:
            return FakeCompleted("missing\t\t\t")
        return FakeCompleted("opened_tab\t101\t202\t303")

    monkeypatch.setattr(iterm2.subprocess, "run", fake_run)

    result = iterm2.open_workspace("/tmp/project", "nvim .", project_id="void")

    assert result["ok"] is True
    assert result["action"] == "opened_tab"
    assert "create tab with default profile" in scripts[2]
    assert 'set name of s to "void-workspace:void"' in scripts[2]
    assert 'write text "nvim ."' in scripts[2]


def test_no_existing_window_falls_back_to_new_window(monkeypatch):
    _macos(monkeypatch)

    def fake_run(args: list[str], **kwargs: Any) -> FakeCompleted:
        script = kwargs["input"]
        if 'application "iTerm2" is running' in script:
            return FakeCompleted("false")
        if "repeat with w in windows" in script:
            return FakeCompleted("missing\t\t\t")
        assert 'desiredMode is "window" or (count of windows) is 0' in script
        return FakeCompleted("opened_window\t101\t202\t303")

    monkeypatch.setattr(iterm2.subprocess, "run", fake_run)

    result = iterm2.open_workspace("/tmp/project", "nvim .", project_id="void")

    assert result["ok"] is True
    assert result["action"] == "opened_window"


def test_open_mode_window_creates_window(monkeypatch):
    _macos(monkeypatch)

    def fake_run(args: list[str], **kwargs: Any) -> FakeCompleted:
        script = kwargs["input"]
        if 'application "iTerm2" is running' in script:
            return FakeCompleted("true")
        if "repeat with w in windows" in script:
            return FakeCompleted("missing\t\t\t")
        assert 'set desiredMode to "window"' in script
        return FakeCompleted("opened_window\t101\t202\t303")

    monkeypatch.setattr(iterm2.subprocess, "run", fake_run)

    result = iterm2.open_workspace("/tmp/project", "nvim .", project_id="void", open_mode="window")

    assert result["ok"] is True
    assert result["action"] == "opened_window"


def test_profile_is_passed_safely(monkeypatch):
    _macos(monkeypatch)
    scripts: list[str] = []

    def fake_run(args: list[str], **kwargs: Any) -> FakeCompleted:
        scripts.append(kwargs["input"])
        if len(scripts) == 1:
            return FakeCompleted("true")
        if len(scripts) == 2:
            return FakeCompleted("missing\t\t\t")
        return FakeCompleted("opened_tab\t101\t202\t303")

    monkeypatch.setattr(iterm2.subprocess, "run", fake_run)

    result = iterm2.open_workspace(
        "/tmp/project",
        'echo "hello"',
        project_id="void",
        profile='Default "Dev"',
    )

    assert result["ok"] is True
    assert 'profile "Default \\"Dev\\""' in scripts[2]
    assert 'write text "echo \\"hello\\""' in scripts[2]


def test_valid_window_bounds_are_applied(monkeypatch):
    _macos(monkeypatch)
    scripts: list[str] = []

    def fake_run(args: list[str], **kwargs: Any) -> FakeCompleted:
        scripts.append(kwargs["input"])
        if len(scripts) == 1:
            return FakeCompleted("true")
        return FakeCompleted("found\t101\t202\t303")

    monkeypatch.setattr(iterm2.subprocess, "run", fake_run)

    result = iterm2.open_workspace(
        "/tmp/project",
        "nvim .",
        project_id="void",
        window_bounds={"left": 100, "top": 80, "right": 1500, "bottom": 950},
    )

    assert result["ok"] is True
    assert "set bounds of w to {100, 80, 1500, 950}" in scripts[1]


def test_invalid_window_bounds_are_rejected(monkeypatch):
    _macos(monkeypatch)

    result = iterm2.open_workspace(
        "/tmp/project",
        "nvim .",
        project_id="void",
        window_bounds={"left": 100, "top": 80, "right": 50, "bottom": 950},
    )

    assert result["ok"] is False
    assert "window_bounds" in result["message"]


def test_run_applescript_handles_timeout(monkeypatch):
    _macos(monkeypatch)

    def fake_run(args: list[str], **kwargs: Any):
        raise subprocess.TimeoutExpired(args, timeout=1)

    monkeypatch.setattr(iterm2.subprocess, "run", fake_run)

    result = iterm2.open_workspace("/tmp/project", "nvim .", project_id="void")

    assert result["ok"] is False
    assert "timed out" in result["message"]
