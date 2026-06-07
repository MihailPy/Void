"""Safety helpers for filesystem-bound built-in tools."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "void"
MEMORY_DIR = PACKAGE_ROOT / "memory"

IGNORED_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".DS_Store",
}


def ensure_memory_files() -> None:
    """Create canonical memory files if they do not exist."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    defaults = {
        "session.md": "# Session Memory\n\n",
        "facts.md": "# Facts Memory\n\n",
        "project.md": (
            "# Project Memory\n\n"
            "## Current State\n\n"
            "- Void is being migrated to a deterministic, registry-based core.\n"
        ),
    }

    for filename, content in defaults.items():
        path = MEMORY_DIR / filename
        if not path.exists():
            path.write_text(content, encoding="utf-8")


def safe_project_path(path: str = ".") -> Path:
    """Resolve a user path and ensure it stays inside the project root."""
    if "\x00" in path:
        raise ValueError("Invalid path")

    candidate = Path(path)
    if ".." in candidate.parts:
        raise ValueError("Path traversal is forbidden")

    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (PROJECT_ROOT / candidate).resolve()

    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError("Access outside the project is forbidden") from error

    return resolved


def is_ignored(path: Path) -> bool:
    return any(part in IGNORED_NAMES for part in path.parts)
