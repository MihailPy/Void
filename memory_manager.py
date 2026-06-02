from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).parent.resolve()
MEMORY_DIR = BASE_DIR / "memory"
SESSION_PATH = MEMORY_DIR / "session.md"
FACTS_PATH = MEMORY_DIR / "facts.md"


def ensure_memory() -> None:
    MEMORY_DIR.mkdir(exist_ok=True)

    if not SESSION_PATH.exists():
        SESSION_PATH.write_text("# Session Memory\n\n", encoding="utf-8")


def read_short_memory() -> str:
    ensure_memory()
    return SESSION_PATH.read_text(encoding="utf-8")


def append_short_memory(title: str, content: str) -> None:
    ensure_memory()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entry = f"""
## {title}

Time: {timestamp}

{content}

---
"""

    with SESSION_PATH.open("a", encoding="utf-8") as file:
        file.write(entry)


def clear_short_memory() -> None:
    MEMORY_DIR.mkdir(exist_ok=True)
    SESSION_PATH.write_text("# Session Memory\n\n", encoding="utf-8")


def ensure_facts_memory() -> None:
    MEMORY_DIR.mkdir(exist_ok=True)

    if not FACTS_PATH.exists():
        FACTS_PATH.write_text("# Medium-Term Memory\n\n", encoding="utf-8")


def read_medium_memory() -> str:
    ensure_facts_memory()
    return FACTS_PATH.read_text(encoding="utf-8")


def append_medium_memory(fact: str) -> str:
    ensure_facts_memory()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entry = f"- {fact} _(saved: {timestamp})_\n"

    with FACTS_PATH.open("a", encoding="utf-8") as file:
        file.write(entry)

    return "Факт сохранён в medium-term memory."


def clear_medium_memory() -> None:
    MEMORY_DIR.mkdir(exist_ok=True)
    FACTS_PATH.write_text("# Medium-Term Memory\n\n", encoding="utf-8")


PROJECT_PATH = MEMORY_DIR / "project.md"


def ensure_project_memory() -> None:
    MEMORY_DIR.mkdir(exist_ok=True)

    if not PROJECT_PATH.exists():
        PROJECT_PATH.write_text(
            """# Project Memory

## Current Version

Void v0.3

## Implemented

- Agent Loop
- Structured JSON output
- Short-term memory
- Medium-term memory

## Known Problems

- 

## Decisions

- 

## Next Tasks

- 

""",
            encoding="utf-8",
        )


def read_project_memory() -> str:
    ensure_project_memory()
    return PROJECT_PATH.read_text(encoding="utf-8")


def update_project_memory(content: str) -> str:
    ensure_project_memory()
    PROJECT_PATH.write_text(content, encoding="utf-8")
    return "Project memory обновлена."
