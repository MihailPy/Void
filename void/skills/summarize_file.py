"""Skill for deterministic file summaries."""

import ast
import re
from pathlib import Path

from void.core.safety import IGNORED_NAMES, safe_project_path
from void.skills.types import SkillDefinition, SkillResult

MAX_ANALYSIS_LINES = 500


def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def _extract_path(user_input: str) -> str | None:
    patterns = (
        r"(?:опиши файл|объясни файл|проанализируй файл|что делает файл)\s+(.+)$",
        r"(?:describe file|explain file|analyze file|what does file)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, user_input, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _clean(match.group(1))
    return None


def _match(user_input: str) -> SkillResult:
    path = _extract_path(user_input)
    if path:
        return SkillResult(
            ok=True,
            content="Matched summarize_file.",
            data={
                "confidence": 0.93,
                "arguments": {"path": path},
                "reason": "User asks to explain or analyze a specific file.",
            },
        )
    return SkillResult(ok=False, content="", data={"confidence": 0.0})


def _display_path(path: Path) -> str:
    return str(path.relative_to(safe_project_path(".")))


def _important_features(lines: list[str]) -> list[str]:
    features: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            features.append(line)
        elif line.startswith(('"""', "'''")):
            features.append(line.strip('"').strip("'"))
        elif re.match(r"^(class|def|async def)\s+", line):
            features.append(line)
        elif line.startswith(("if __name__", "from ", "import ")):
            features.append(line)
        if len(features) >= 8:
            break
    return features


def _python_symbols(content: str) -> tuple[list[str], list[str], list[str]]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return [], [], []

    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(alias.name for alias in node.names)
            imports.append(f"{module}: {names}" if module else names)

    return sorted(set(functions)), sorted(set(classes)), sorted(set(imports))


def summarize_file(
    path: str | None = None,
    user_input: str | None = None,
    match_only: bool = False,
) -> SkillResult:
    if match_only:
        return _match(user_input or "")
    if not path:
        return SkillResult(ok=False, content="File path was not provided.")

    try:
        file_path = safe_project_path(path)
    except ValueError as error:
        return SkillResult(ok=False, content=str(error))

    if any(part in IGNORED_NAMES for part in file_path.parts):
        return SkillResult(ok=False, content=f"Path is ignored: {path}")
    if not file_path.exists():
        return SkillResult(ok=False, content=f"File not found: {path}")
    if not file_path.is_file():
        return SkillResult(ok=False, content=f"Not a file: {path}")

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return SkillResult(ok=False, content=f"File is not valid UTF-8 text: {path}")

    all_lines = content.splitlines()
    analysis_lines = all_lines[:MAX_ANALYSIS_LINES]
    analyzed_content = "\n".join(analysis_lines)
    truncated = len(all_lines) > MAX_ANALYSIS_LINES

    lines = [
        f"File summary: {_display_path(file_path)}",
        f"Size: {file_path.stat().st_size} bytes",
        f"Lines: {len(all_lines)}",
    ]
    if truncated:
        lines.append(f"Analyzed: first {MAX_ANALYSIS_LINES} lines only")

    features = _important_features(analysis_lines)
    lines.append("")
    lines.append("Important signs:")
    lines.extend(f"- {feature}" for feature in features) if features else lines.append(
        "- none"
    )

    if file_path.suffix == ".py":
        functions, classes, imports = _python_symbols(analyzed_content)
        lines.append("")
        lines.append("Python imports:")
        lines.extend(f"- {item}" for item in imports) if imports else lines.append(
            "- none"
        )
        lines.append("")
        lines.append("Python classes:")
        lines.extend(f"- {item}" for item in classes) if classes else lines.append(
            "- none"
        )
        lines.append("")
        lines.append("Python functions:")
        lines.extend(f"- {item}" for item in functions) if functions else lines.append(
            "- none"
        )

    return SkillResult(
        ok=True,
        content="\n".join(lines),
        data={
            "path": _display_path(file_path),
            "lines": len(all_lines),
            "truncated": truncated,
        },
    )


def definitions() -> list[SkillDefinition]:
    return [
        SkillDefinition(
            name="summarize_file",
            description="Describe and inspect a specific project file without LLM.",
            keywords=[
                "опиши файл",
                "объясни файл",
                "что делает файл",
                "проанализируй файл",
            ],
            function=summarize_file,
            terminal=True,
        )
    ]
