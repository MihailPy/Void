import ast
import json
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).parent.resolve()
TOOLS_DIR = BASE_DIR / "tools"


BLOCKED_IMPORTS = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "socket",
    "pathlib",
    "requests",
}

BLOCKED_CALLS = {
    "open",
    "eval",
    "exec",
    "compile",
    "__import__",
    "input",
}


def validate_tool_code(code: str) -> tuple[bool, str]:
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return False, f"Syntax error: {error}"

    has_run_function = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BLOCKED_IMPORTS:
                    return False, f"Blocked import: {alias.name}"

        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in BLOCKED_IMPORTS:
                return False, f"Blocked import: {node.module}"

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in BLOCKED_CALLS:
                    return False, f"Blocked call: {node.func.id}"

        if isinstance(node, ast.FunctionDef):
            if node.name == "run":
                has_run_function = True

    if not has_run_function:
        return False, "Tool must contain function: run(args)"

    return True, "OK"


def create_self_tool(name: str, code: str) -> dict:
    if not name.isidentifier():
        return {
            "ok": False,
            "error": "Tool name must be valid Python identifier",
        }

    is_valid, message = validate_tool_code(code)

    if not is_valid:
        return {
            "ok": False,
            "error": message,
        }

    TOOLS_DIR.mkdir(exist_ok=True)

    tool_path = TOOLS_DIR / f"{name}.py"
    tool_path.write_text(code, encoding="utf-8")

    return {
        "ok": True,
        "message": f"Self-tool created: {name}",
        "path": str(tool_path),
    }


def list_self_tools() -> dict:
    TOOLS_DIR.mkdir(exist_ok=True)

    tools = []

    for path in TOOLS_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue

        tools.append(path.stem)

    return {
        "ok": True,
        "tools": tools,
    }


def run_self_tool(name: str, args: dict | None = None) -> dict:
    if args is None:
        args = {}

    if not name.isidentifier():
        return {
            "ok": False,
            "error": "Invalid tool name",
        }

    tool_path = TOOLS_DIR / f"{name}.py"

    if not tool_path.exists():
        return {
            "ok": False,
            "error": f"Tool not found: {name}",
        }

    runner_code = f"""
import json
import importlib.util

tool_path = {str(tool_path)!r}
args = json.loads({json.dumps(json.dumps(args))!r})

spec = importlib.util.spec_from_file_location("self_tool", tool_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

result = module.run(args)
print(json.dumps(result, ensure_ascii=False))
"""

    try:
        result = subprocess.run(
            ["python", "-c", runner_code],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=TOOLS_DIR,
        )

        if result.returncode != 0:
            return {
                "ok": False,
                "error": result.stderr,
            }

        return {
            "ok": True,
            "result": json.loads(result.stdout),
        }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "Tool execution timeout",
        }

    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
        }
