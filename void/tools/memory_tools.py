"""Markdown-backed memory tools."""

from datetime import datetime

from void.core.safety import MEMORY_DIR, ensure_memory_files
from void.core.types import ToolDefinition, ToolResult

MAX_SESSION_ENTRY_CHARS = 3000


def _path(name: str):
    ensure_memory_files()
    return MEMORY_DIR / name


def _truncate(content: str) -> str:
    if len(content) <= MAX_SESSION_ENTRY_CHARS:
        return content
    return content[:MAX_SESSION_ENTRY_CHARS] + "\n\n[truncated]"


def remember_fact(fact: str) -> ToolResult:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _path("facts.md").open("a", encoding="utf-8") as file:
        file.write(f"- {fact} _(saved: {timestamp})_\n")
    return ToolResult(ok=True, content="Fact saved.", terminal=True)


def read_facts() -> ToolResult:
    return ToolResult(ok=True, content=_path("facts.md").read_text(encoding="utf-8"))


def update_project(content: str) -> ToolResult:
    _path("project.md").write_text(content, encoding="utf-8")
    return ToolResult(ok=True, content="Project memory updated.", terminal=True)


def append_project_note(note: str) -> ToolResult:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path = _path("project.md")
    if path.exists() and path.stat().st_size > 0:
        with path.open("rb+") as file:
            file.seek(-1, 2)
            if file.read(1) != b"\n":
                file.write(b"\n")

    with path.open("a", encoding="utf-8") as file:
        file.write(f"- {note} _(saved: {timestamp})_\n")
    return ToolResult(ok=True, content="Project note appended.", terminal=True)


def read_project() -> ToolResult:
    return ToolResult(ok=True, content=_path("project.md").read_text(encoding="utf-8"))


def append_session(title: str, content: str) -> ToolResult:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"## {title}\n\nTime: {timestamp}\n\n{_truncate(content)}\n\n---\n\n"
    with _path("session.md").open("a", encoding="utf-8") as file:
        file.write(entry)
    return ToolResult(ok=True, content="Session entry appended.")


def clear_session() -> ToolResult:
    _path("session.md").write_text("# Session Memory\n\n", encoding="utf-8")
    return ToolResult(ok=True, content="Session memory cleared.", terminal=True)


def clear_facts() -> ToolResult:
    _path("facts.md").write_text("# Facts Memory\n\n", encoding="utf-8")
    return ToolResult(ok=True, content="Facts memory cleared.", terminal=True)


def definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition("remember_fact", "Save a medium-term fact.", remember_fact, terminal=True),
        ToolDefinition("read_facts", "Read saved facts.", read_facts),
        ToolDefinition("update_project", "Replace project memory.", update_project, terminal=True),
        ToolDefinition(
            "append_project_note",
            "Append a note to project memory.",
            append_project_note,
            terminal=True,
        ),
        ToolDefinition("read_project", "Read project memory.", read_project),
        ToolDefinition("append_session", "Append an entry to session memory.", append_session),
        ToolDefinition("clear_session", "Clear session memory.", clear_session, terminal=True),
        ToolDefinition("clear_facts", "Clear facts memory.", clear_facts, terminal=True),
    ]
