"""Skill for deterministic project-wide text search."""

import re
from pathlib import Path

from void.core.safety import IGNORED_NAMES, safe_project_path
from void.skills.types import SkillDefinition, SkillResult

MAX_MATCHES = 30


def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def _extract_query(user_input: str) -> str | None:
    patterns = (
        r"^найди\s+(.+?)\s+в\s+проекте$",
        r"^найди\s+текст\s+(.+)$",
        r"^поиск\s+(.+)$",
        r"^где\s+используется\s+(.+)$",
        r"^find\s+(.+?)\s+in\s+(?:the\s+)?project$",
        r"^search\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, user_input, flags=re.IGNORECASE | re.DOTALL)
        if match:
            query = _clean(match.group(1))
            return query or None
    return None


def _match(user_input: str) -> SkillResult:
    query = _extract_query(user_input)
    if query:
        return SkillResult(
            ok=True,
            content="Matched find_text.",
            data={
                "confidence": 0.92,
                "arguments": {"query": query},
                "reason": "User asks to search text in the project.",
            },
        )
    return SkillResult(ok=False, content="", data={"confidence": 0.0})


def _is_text_file(path: Path) -> bool:
    try:
        with path.open("rb") as file:
            chunk = file.read(2048)
    except OSError:
        return False
    return b"\x00" not in chunk


def _should_skip(path: Path) -> bool:
    return any(part in IGNORED_NAMES for part in path.parts)


def find_text(
    query: str | None = None,
    user_input: str | None = None,
    match_only: bool = False,
) -> SkillResult:
    if match_only:
        return _match(user_input or "")
    if not query:
        return SkillResult(ok=False, content="Search query was not provided.")

    root = safe_project_path(".")
    query_lower = query.lower()
    matches: list[dict[str, str | int]] = []

    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if _should_skip(relative) or not path.is_file() or not _is_text_file(path):
            continue

        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        for line_number, line in enumerate(lines, start=1):
            if query_lower not in line.lower():
                continue
            fragment = line.strip()
            if len(fragment) > 160:
                fragment = fragment[:157] + "..."
            matches.append(
                {
                    "path": str(relative),
                    "line": line_number,
                    "fragment": fragment,
                }
            )
            if len(matches) >= MAX_MATCHES:
                break
        if len(matches) >= MAX_MATCHES:
            break

    if not matches:
        return SkillResult(ok=True, content=f"No matches found for: {query}", data={"matches": []})

    lines_out = [f"Search results for: {query}", ""]
    for item in matches:
        lines_out.append(f"{item['path']}:{item['line']}: {item['fragment']}")
    if len(matches) >= MAX_MATCHES:
        lines_out.append("")
        lines_out.append(f"Limited to first {MAX_MATCHES} matches.")

    return SkillResult(ok=True, content="\n".join(lines_out), data={"matches": matches})


def definitions() -> list[SkillDefinition]:
    return [
        SkillDefinition(
            name="find_text",
            description="Search for a string across project text files without LLM.",
            keywords=["найди", "поиск", "где используется", "найди текст"],
            function=find_text,
            terminal=True,
        )
    ]
