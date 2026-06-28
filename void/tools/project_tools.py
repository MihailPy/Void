"""Project inspection and context tools."""

from collections import Counter
from pathlib import Path

from void.core import project_context
from void.core.safety import IGNORED_NAMES, safe_project_path
from void.core.types import ToolDefinition, ToolResult


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
        return ToolResult(ok=False, content=result["error"])

    selected = result["project"]
    return ToolResult(
        ok=True,
        content=f"Current project set to {selected['name']} ({selected['id']}).",
        data={"project": selected},
    )


def describe_current_project() -> ToolResult:
    try:
        project = project_context.get_current_project()
        description = project_context.describe_current_project()
    except ValueError as error:
        return ToolResult(ok=False, content=str(error))

    return ToolResult(ok=True, content=description, data={"project": project})


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
            "describe_current_project",
            "Describe the current project context.",
            describe_current_project,
            category="project",
            risk_level="read",
        ),
    ]
