"""Skill for deterministic project reports."""

import re
from collections import Counter
from pathlib import Path

from void.core.safety import IGNORED_NAMES, safe_project_path
from void.skills.types import SkillDefinition, SkillResult


def _match(user_input: str) -> SkillResult:
    text = user_input.strip().lower()
    phrases = (
        "сделай отчет по проекту",
        "сделай отчёт по проекту",
        "составь отчет по проекту",
        "составь отчёт по проекту",
        "опиши проект",
        "что есть в проекте",
        "обзор проекта",
    )
    if any(phrase in text for phrase in phrases):
        return SkillResult(
            ok=True,
            content="Matched project_report.",
            data={
                "confidence": 0.9,
                "arguments": {},
                "reason": "User asks for a project overview report.",
            },
        )
    return SkillResult(ok=False, content="", data={"confidence": 0.0})


def _should_skip(path: Path) -> bool:
    return any(part in IGNORED_NAMES for part in path.parts)


def _read_optional(path: Path, limit: int = 1200) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""
    content = content.strip()
    if len(content) > limit:
        return content[:limit].rstrip() + "\n[truncated]"
    return content


def _stats(root: Path) -> tuple[int, int, Counter[str], list[str]]:
    file_count = 0
    folder_count = 0
    extensions: Counter[str] = Counter()

    for item in root.rglob("*"):
        relative = item.relative_to(root)
        if _should_skip(relative):
            continue
        if item.is_dir():
            folder_count += 1
        elif item.is_file():
            file_count += 1
            extensions[item.suffix.lower() or "[no extension]"] += 1

    top_level = []
    for item in sorted(root.iterdir(), key=lambda value: (not value.is_dir(), value.name.lower())):
        if item.name in IGNORED_NAMES:
            continue
        prefix = "[DIR]" if item.is_dir() else "[FILE]"
        top_level.append(f"{prefix} {item.name}")

    return file_count, folder_count, extensions, top_level


def _components(root: Path) -> list[str]:
    candidates = (
        "void/core/agent.py",
        "void/core/router.py",
        "void/core/registry.py",
        "void/core/llm.py",
        "void/tools",
        "void/memory",
        "void/skills",
    )
    labels = {
        "void/core/agent.py": "single-action agent runtime",
        "void/core/router.py": "deterministic router",
        "void/core/registry.py": "tool registry",
        "void/core/llm.py": "LLM fallback",
        "void/tools": "built-in tools",
        "void/memory": "markdown-backed memory",
        "void/skills": "deterministic skill system",
    }
    return [labels[item] for item in candidates if (root / item).exists()]


def _next_tasks(project_memory: str) -> list[str]:
    lines = project_memory.splitlines()
    tasks: list[str] = []
    in_next = False
    for line in lines:
        if re.match(r"^##\s+", line):
            in_next = "next" in line.lower() or "зада" in line.lower()
            continue
        if in_next and line.strip().startswith("-"):
            tasks.append(line.strip())
    return tasks


def project_report(user_input: str | None = None, match_only: bool = False) -> SkillResult:
    if match_only:
        return _match(user_input or "")

    root = safe_project_path(".")
    readme = _read_optional(root / "README.md")
    project_memory = _read_optional(root / "memory" / "project.md", limit=2000)
    if not project_memory:
        project_memory = _read_optional(root / "void" / "memory" / "project.md", limit=2000)
    file_count, folder_count, extensions, top_level = _stats(root)
    components = _components(root)
    next_tasks = _next_tasks(project_memory)

    extension_lines = [
        f"- {extension}: {count}" for extension, count in sorted(extensions.items())
    ]
    component_lines = [f"- {component}" for component in components] or ["- none"]
    task_lines = next_tasks or ["- none found in project memory"]

    lines = [
        "Project report",
        "",
        "Short description:",
        readme or "No README.md description found.",
        "",
        "Top-level structure:",
        *(top_level or ["- empty"]),
        "",
        "File statistics:",
        f"- Files: {file_count}",
        f"- Folders: {folder_count}",
        "",
        "Files by extension:",
        *(extension_lines or ["- none"]),
        "",
        "Implemented components:",
        *component_lines,
        "",
        "Known next tasks:",
        *task_lines,
    ]

    return SkillResult(
        ok=True,
        content="\n".join(lines),
        data={"files": file_count, "folders": folder_count, "extensions": dict(extensions)},
    )


def definitions() -> list[SkillDefinition]:
    return [
        SkillDefinition(
            name="project_report",
            description="Build a concise deterministic project report without LLM.",
            keywords=[
                "сделай отчет по проекту",
                "составь отчёт по проекту",
                "опиши проект",
                "что есть в проекте",
                "обзор проекта",
            ],
            function=project_report,
            terminal=True,
        )
    ]
