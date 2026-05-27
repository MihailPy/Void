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
    return "План сохранён в memory/current_plan.md"


def read_plan() -> str:
    if not PLAN_PATH.exists():
        return "План ещё не создан."

    return PLAN_PATH.read_text(encoding="utf-8")


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
    return f"Шаг плана {step_number} отмечен как выполненный."


def has_unfinished_steps() -> bool:
    if not PLAN_PATH.exists():
        return False

    text = PLAN_PATH.read_text(encoding="utf-8")
    return "- [ ]" in text
