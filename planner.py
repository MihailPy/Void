import re
from pathlib import Path


BASE_DIR = Path(__file__).parent.resolve()
PLAN_PATH = BASE_DIR / "memory" / "current_plan.md"


def save_plan(steps: list[str]) -> str:
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)

    content = "# Current Plan\n\n"
    for index, step in enumerate(steps, start=1):
        content += f"- [ ] {index}. {step}\n"

    PLAN_PATH.write_text(content, encoding="utf-8")
    return "План сохранён."


def read_plan() -> str:
    if not PLAN_PATH.exists():
        return "План ещё не создан."

    return PLAN_PATH.read_text(encoding="utf-8")


def clear_plan() -> str:
    if PLAN_PATH.exists():
        PLAN_PATH.unlink()

    return "План очищен."


def has_plan() -> bool:
    return PLAN_PATH.exists()


def has_unfinished_steps() -> bool:
    if not PLAN_PATH.exists():
        return False

    return "- [ ]" in PLAN_PATH.read_text(encoding="utf-8")


def get_unfinished_steps() -> list[tuple[int, str]]:
    if not PLAN_PATH.exists():
        return []

    text = PLAN_PATH.read_text(encoding="utf-8")
    pattern = r"^- \[ \] (\d+)\. (.+)$"

    return [
        (int(match.group(1)), match.group(2))
        for match in re.finditer(pattern, text, flags=re.MULTILINE)
    ]


def mark_plan_step_done(step_number: int) -> str:
    if not PLAN_PATH.exists():
        return "План ещё не создан."

    text = PLAN_PATH.read_text(encoding="utf-8")

    pattern = rf"^- \[ \] {step_number}\. "
    replacement = f"- [x] {step_number}. "

    new_text, count = re.subn(
        pattern,
        replacement,
        text,
        count=1,
        flags=re.MULTILINE,
    )

    if count == 0:
        return f"Не удалось найти невыполненный шаг {step_number}."

    PLAN_PATH.write_text(new_text, encoding="utf-8")
    return f"Шаг плана {step_number} выполнен."


def mark_next_step_done() -> str:
    unfinished = get_unfinished_steps()

    if not unfinished:
        return "Нет невыполненных шагов."

    step_number, _ = unfinished[0]
    return mark_plan_step_done(step_number)


def is_final_step(text: str) -> bool:
    text = text.lower()

    keywords = [
        "ответ",
        "финальный",
        "итог",
        "результат",
        "вывод",
        "сообщить",
        "описать",
        "объяснить",
    ]

    return any(keyword in text for keyword in keywords)
