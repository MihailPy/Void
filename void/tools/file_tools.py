"""Safe one-shot file tools."""

from pathlib import Path

from void.core.safety import IGNORED_NAMES, safe_project_path
from void.core.types import ToolDefinition, ToolResult


def _display_path(path: Path) -> str:
    return str(path.relative_to(safe_project_path(".")))


def read_file(path: str) -> ToolResult:
    try:
        file_path = safe_project_path(path)
    except ValueError as error:
        return ToolResult(ok=False, content=str(error))

    if any(part in IGNORED_NAMES for part in file_path.parts):
        return ToolResult(ok=False, content=f"Path is ignored: {path}")
    if not file_path.exists():
        return ToolResult(ok=False, content=f"File not found: {path}")
    if not file_path.is_file():
        return ToolResult(ok=False, content=f"Not a file: {path}")

    return ToolResult(ok=True, content=file_path.read_text(encoding="utf-8"))


def write_file(path: str, content: str) -> ToolResult:
    try:
        file_path = safe_project_path(path)
    except ValueError as error:
        return ToolResult(ok=False, content=str(error))

    if any(part in IGNORED_NAMES for part in file_path.parts):
        return ToolResult(ok=False, content=f"Path is ignored: {path}")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return ToolResult(ok=True, content=f"File written: {_display_path(file_path)}")


def list_files(path: str = ".") -> ToolResult:
    try:
        dir_path = safe_project_path(path)
    except ValueError as error:
        return ToolResult(ok=False, content=str(error))

    if any(part in IGNORED_NAMES for part in dir_path.parts):
        return ToolResult(ok=False, content=f"Path is ignored: {path}")
    if not dir_path.exists():
        return ToolResult(ok=False, content=f"Directory not found: {path}")
    if not dir_path.is_dir():
        return ToolResult(ok=False, content=f"Not a directory: {path}")

    lines: list[str] = []
    for item in sorted(
        dir_path.iterdir(),
        key=lambda value: (not value.is_dir(), value.name.lower()),
    ):
        if item.name in IGNORED_NAMES:
            continue
        prefix = "[DIR]" if item.is_dir() else "[FILE]"
        lines.append(f"{prefix} {item.name}")

    return ToolResult(ok=True, content="\n".join(lines) if lines else "Directory is empty")


def definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            "read_file",
            "Read a UTF-8 file inside the project.",
            read_file,
            category="filesystem",
            risk_level="read",
        ),
        ToolDefinition(
            "write_file",
            "Write a UTF-8 file inside the project.",
            write_file,
            requires_confirmation=True,
            category="filesystem",
            risk_level="write",
        ),
        ToolDefinition(
            "list_files",
            "List one directory level inside the project.",
            list_files,
            category="filesystem",
            risk_level="read",
        ),
    ]
