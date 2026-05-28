# Session Memory


## User Request

Time: 2026-05-28 17:44:14

Меня зовут Михаил, а проект называется Void

---

## User Request

Time: 2026-05-28 17:49:09

Как называется мой проект?

---

## Agent Action

Time: 2026-05-28 17:49:22

Action: final_answer
Reason: Информация о названии проекта уже есть в MEMORY — пользователь написал, что проект называется Void. Это простой вопрос, который можно ответить напрямую без использования инструментов.
Result:
Ваш проект называется Void.

---

## Final Answer

Time: 2026-05-28 17:49:22

Ваш проект называется Void.

---

## User Request

Time: 2026-05-28 17:50:11

Хорошо. Сделай описание файла memory_manager.py

---

## Agent Action

Time: 2026-05-28 17:50:31

Action: read_file
Reason: Пользователь просит описать файл memory_manager.py. Согласно правилам, сначала нужно прочитать содержимое файла с помощью read_file, а затем дать ответ на основе прочитанного.
Result:
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


---

## Agent Action

Time: 2026-05-28 17:50:59

Action: final_answer
Reason: Я прочитал содержимое файла memory_manager.py и теперь могу дать полное описание его функциональности на основе полученного observation.
Result:
Файл memory_manager.py — это утилита для управления сессионной памятью проекта.

Основные функции:

1. **ensure_memory()** — создаёт директорию `memory/` и файл `session.md`, если они не существуют.

2. **read_short_memory()** — читает содержимое файла `memory/session.md` (текущую сессионную память).

3. **append_short_memory(title, content)** — добавляет новый блок памяти с заголовком, временем и контентом в файл.

4. **clear_short_memory()** — очищает файл `session.md`, оставляя только заголовок `# Session Memory`.

Файл использует относительный путь к файлу `memory/session.md` относительно директории проекта.

---

## Final Answer

Time: 2026-05-28 17:50:59

Файл memory_manager.py — это утилита для управления сессионной памятью проекта.

Основные функции:

1. **ensure_memory()** — создаёт директорию `memory/` и файл `session.md`, если они не существуют.

2. **read_short_memory()** — читает содержимое файла `memory/session.md` (текущую сессионную память).

3. **append_short_memory(title, content)** — добавляет новый блок памяти с заголовком, временем и контентом в файл.

4. **clear_short_memory()** — очищает файл `session.md`, оставляя только заголовок `# Session Memory`.

Файл использует относительный путь к файлу `memory/session.md` относительно директории проекта.

---
