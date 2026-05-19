from pathlib import Path


BASE_DIR = Path(__file__).parent.resolve()


def safe_path(path: str) -> Path:
    full_path = (BASE_DIR / path).resolve()

    if not str(full_path).startswith(str(BASE_DIR)):
        raise ValueError("Доступ за пределы проекта запрещён")

    return full_path


def answer(text: str) -> str:
    return text


def read_file(path: str) -> str:
    file_path = safe_path(path)

    if not file_path.exists():
        return f"Файл не найден: {path}"

    if not file_path.is_file():
        return f"Это не файл: {path}"

    return file_path.read_text(encoding="utf-8")


def write_file(path: str, content: str) -> str:
    file_path = safe_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    return f"Файл записан: {path}"


def list_files(path: str) -> str:
    dir_path = safe_path(path)

    if not dir_path.exists():
        return f"Папка не найдена: {path}"

    if not dir_path.is_dir():
        return f"Это не папка: {path}"

    items = []

    for item in dir_path.iterdir():
        prefix = "[DIR]" if item.is_dir() else "[FILE]"
        items.append(f"{prefix} {item.name}")

    return "\n".join(items) if items else "Папка пустая"
