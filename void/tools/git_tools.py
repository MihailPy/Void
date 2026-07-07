"""Safe Git tools for the current Void project."""

from __future__ import annotations

import subprocess
from pathlib import Path

from void.core import activity_history
from void.core.safety import PROJECT_ROOT, safe_project_path
from void.core.types import ToolDefinition, ToolResult

FORBIDDEN_GIT_COMMANDS = {
    "push",
    "pull",
    "reset",
    "checkout",
    "switch",
    "merge",
    "rebase",
    "clean",
    "remote",
    "config",
}

SAFETY_ERROR = "This git command is not supported for safety reasons."


def _resolve_git_cwd(cwd: str) -> Path:
    resolved = safe_project_path(cwd)
    if not resolved.exists():
        raise ValueError(f"Path not found: {cwd}")
    if not resolved.is_dir():
        raise ValueError(f"Not a directory: {cwd}")
    return resolved


def run_git_command(args: list[str], cwd: str = ".") -> ToolResult:
    """Run a bounded Git command without shell expansion."""
    try:
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            return ToolResult(ok=False, content="Git arguments must be a list of strings.")

        git_args = args[1:] if args[:1] == ["git"] else args
        if not git_args:
            return ToolResult(ok=False, content="Git command is required.")

        command_name = git_args[0].lower()
        if command_name in FORBIDDEN_GIT_COMMANDS:
            return ToolResult(ok=False, content=SAFETY_ERROR, terminal=True)

        resolved_cwd = _resolve_git_cwd(cwd)
        command = ["git", *git_args]
        completed = subprocess.run(
            command,
            cwd=resolved_cwd,
            shell=False,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        parts = []
        if stdout:
            parts.append(stdout)
        if stderr:
            parts.append(stderr)
        content = "\n".join(parts) if parts else ""
        return ToolResult(
            ok=completed.returncode == 0,
            content=content,
            data={
                "command": command,
                "cwd": str(resolved_cwd.relative_to(PROJECT_ROOT)),
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
            terminal=True,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(ok=False, content="Git command timed out.", terminal=True)
    except Exception as error:
        return ToolResult(ok=False, content=f"Git command failed: {error}", terminal=True)


def _truncate(value: str, max_chars: int) -> str:
    limit = max(0, int(max_chars))
    if len(value) <= limit:
        return value
    return value[:limit] + "\n[output truncated]"


def git_status(cwd: str = ".") -> ToolResult:
    return run_git_command(["status", "--short", "--branch"], cwd=cwd)


def git_diff(cwd: str = ".", staged: bool = False, max_chars: int = 12000) -> ToolResult:
    args = ["diff", "--staged"] if staged else ["diff"]
    result = run_git_command(args, cwd=cwd)
    if result.content:
        result.content = _truncate(result.content, max_chars)
    return result


def git_log(cwd: str = ".", limit: int = 10) -> ToolResult:
    safe_limit = min(50, max(1, int(limit)))
    return run_git_command(["log", "--oneline", "-n", str(safe_limit)], cwd=cwd)


def git_current_branch(cwd: str = ".") -> ToolResult:
    return run_git_command(["branch", "--show-current"], cwd=cwd)


def _status_paths(status_output: str) -> list[str]:
    paths: list[str] = []
    for line in status_output.splitlines():
        if not line or line.startswith("##"):
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            paths.append(path)
    return paths


def _commit_area(paths: list[str], diff: str) -> str | None:
    searchable = "\n".join(paths) + "\n" + diff
    lowered = searchable.lower()
    if "git" in lowered:
        return "git"
    if "browser" in lowered:
        return "browser"
    if "void/tools/" in lowered or "/tools/" in lowered:
        return "tools"
    if "void/core/" in lowered or "/core/" in lowered:
        return "core"
    return None


def git_suggest_commit_message(cwd: str = ".") -> ToolResult:
    status = git_status(cwd)
    if not status.ok:
        return status

    staged_diff = git_diff(cwd=cwd, staged=True)
    diff = staged_diff.content if staged_diff.ok else ""
    diff_source = "staged"
    if not diff.strip():
        unstaged_diff = git_diff(cwd=cwd, staged=False)
        diff = unstaged_diff.content if unstaged_diff.ok else ""
        diff_source = "unstaged"

    paths = _status_paths(status.content)
    lowered_paths = [path.lower() for path in paths]
    if any(path.startswith("docs/") or path == "readme.md" for path in lowered_paths):
        message = "Update documentation"
    elif any("test" in path or path.startswith("tests/") for path in lowered_paths):
        message = "Add or update tests"
    else:
        area = _commit_area(paths, diff)
        if area in {"git", "browser"}:
            message = f"Add {area} capability"
        elif area is not None:
            message = f"Update {area}"
        else:
            message = "Update project files"

    summary = "\n".join(f"- {path}" for path in paths) if paths else "- No changed files"
    return ToolResult(
        ok=True,
        content=(
            f"Suggested commit message: {message}\n\n"
            f"Diff source: {diff_source}\n"
            f"Files:\n{summary}"
        ),
        data={"message": message, "files": paths, "diff_source": diff_source},
        terminal=True,
    )


def git_commit(message: str, cwd: str = ".") -> ToolResult:
    clean_message = str(message).strip()
    if not clean_message:
        activity_history.log_activity(
            "git",
            "failure",
            "Failed to create Git commit",
            {"operation": "commit", "cwd": cwd},
        )
        return ToolResult(ok=False, content="Commit message is required.", terminal=True)
    result = run_git_command(["commit", "-m", clean_message], cwd=cwd)
    activity_history.log_activity(
        "git",
        "success" if result.ok else "failure",
        "Created Git commit" if result.ok else "Failed to create Git commit",
        {"operation": "commit", "cwd": cwd},
    )
    return result


def definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            "git_status",
            "Show safe short Git status for the current project.",
            git_status,
            terminal=True,
            requires_confirmation=False,
            category="git",
            risk_level="read",
        ),
        ToolDefinition(
            "git_diff",
            "Show safe Git diff output for the current project.",
            git_diff,
            terminal=True,
            requires_confirmation=False,
            category="git",
            risk_level="read",
        ),
        ToolDefinition(
            "git_log",
            "Show recent Git commits.",
            git_log,
            terminal=True,
            requires_confirmation=False,
            category="git",
            risk_level="read",
        ),
        ToolDefinition(
            "git_current_branch",
            "Show the current Git branch.",
            git_current_branch,
            terminal=True,
            requires_confirmation=False,
            category="git",
            risk_level="read",
        ),
        ToolDefinition(
            "git_suggest_commit_message",
            "Suggest a simple commit message from Git status and diff.",
            git_suggest_commit_message,
            terminal=True,
            requires_confirmation=False,
            category="git",
            risk_level="read",
        ),
        ToolDefinition(
            "git_commit",
            "Create a Git commit with an explicit message after approval.",
            git_commit,
            terminal=True,
            requires_confirmation=True,
            category="git",
            risk_level="write",
        ),
    ]
