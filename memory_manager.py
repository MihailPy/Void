from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).parent.resolve()
MEMORY_DIR = BASE_DIR / "memory"
SESSION_PATH = MEMORY_DIR / "session.md"


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
