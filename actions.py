from pathlib import Path
import subprocess


BASE_DIR = Path(__file__).parent.resolve()


ALLOWED_COMMANDS = {
    "ls",
    "cat",
    "pwd",
    "curl",
    "grep",
}
BLOCKED_COMMANDS = {
    "rm",
    "mv",
    "chmod",
    "chown",
    "sudo",
    "su",
    "ssh",
    "scp",
    "dd",
    "mkfs",
    "kill",
    "pkill",
}


def run_command(command: list[str], cwd: str = ".") -> dict:
    if not command:
        return {
            "ok": False,
            "error": "Empty command",
        }

    executable = command[0]

    if executable in BLOCKED_COMMANDS:
        return {
            "ok": False,
            "error": f"Command in blocked list: {executable}",
        }

    if executable not in ALLOWED_COMMANDS:
        return {
            "ok": False,
            "error": f"Command not allowed: {executable}",
        }

    try:
        result = subprocess.run(
            command,
            cwd=Path(cwd).resolve(),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        return {
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "Command timed out",
        }

    except FileNotFoundError:
        return {
            "ok": False,
            "error": f"Executable not found: {executable}",
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


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
