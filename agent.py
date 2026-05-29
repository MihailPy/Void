import json
import re

from openai.types.chat import ChatCompletionMessageParam

from actions import (
    complete_plan_step,
    create_plan,
    create_tool,
    get_plan,
    list_files,
    list_tools,
    read_file,
    run_command,
    run_tool,
    write_file,
)
from llm import ask_chatgpt
from memory_manager import append_short_memory, read_short_memory
from planner import (
    clear_plan,
    get_unfinished_steps,
    has_unfinished_steps,
    is_final_step,
    mark_next_step_done,
)
from prompts import SYSTEM_PROMPT

MAX_STEPS = 12
DEBUG = True


def extract_json(text: str) -> str:

    text = text.strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)

    if not match:
        raise ValueError(f"JSON не найден:\n{text}")

    return match.group(0)


def parse_llm_response(raw_response: str) -> dict:
    json_text = extract_json(raw_response)
    return json.loads(json_text)


def execute_action(action_data: dict) -> str | dict:
    action = action_data.get("action")
    arguments = action_data.get("arguments", {})

    if action == "final_answer":
        return arguments.get("text", "")

    if action == "read_file":
        return read_file(arguments["path"])

    if action == "write_file":
        return write_file(
            arguments["path"],
            arguments["content"],
        )

    if action == "list_files":
        return list_files(arguments.get("path", "."))

    if action == "run_command":
        return run_command(
            arguments.get("command", []),
            arguments.get("cwd", "."),
        )

    if action == "create_tool":
        return create_tool(
            arguments["name"],
            arguments["code"],
        )

    if action == "list_tools":
        return list_tools()

    if action == "run_tool":
        return run_tool(
            arguments["name"],
            arguments.get("args", {}),
        )

    if action == "create_plan":
        return create_plan(arguments["steps"])

    if action == "get_plan":
        return get_plan()

    if action == "complete_plan_step":
        return complete_plan_step(arguments["step_number"])

    return f"Неизвестное действие: {action}"


def run_agent(user_input: str) -> str:
    short_memory = read_short_memory()

    append_short_memory(
        "User Request",
        user_input,
    )

    messages: list[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": f"MEMORY:\n{short_memory}",
        },
        {
            "role": "user",
            "content": user_input,
        },
    ]

    plan_required = task_requires_plan(user_input)
    clear_plan()
    plan_created = False
    file_read_required = task_requires_file_read(user_input)
    file_was_read = False

    for step in range(1, MAX_STEPS + 1):
        debug_log("STEP", step)

        raw_response = ask_chatgpt(messages)

        debug_log("RAW LLM RESPONSE", raw_response)

        try:
            action_data = parse_llm_response(raw_response)
        except json.JSONDecodeError:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Твой предыдущий ответ был невалидным JSON. "
                        "Повтори тот же самый action, но верни только корректный JSON без markdown и пояснений."
                    ),
                }
            )
            continue
        except ValueError:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Твой предыдущий ответ не содержал JSON. "
                        "Верни только JSON в формате: "
                        '{"action": "...", "arguments": {}, "reason": "..."}'
                    ),
                }
            )
            continue

        action = action_data.get("action")

        if file_read_required and not file_was_read and action == "final_answer":
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Ошибка управления: пользователь просит описать файл. "
                        "Перед final_answer ты обязан сначала вызвать read_file "
                        "для нужного файла, а затем ответить на основе observation."
                    ),
                }
            )
            continue

        if action == "final_answer" and has_unfinished_steps():
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Ошибка управления: план ещё не завершён. "
                        "Перед final_answer ты обязан вызвать complete_plan_step "
                        "для всех выполненных шагов плана."
                    ),
                }
            )
            continue

        if plan_required and not plan_created and action != "create_plan":
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Ошибка управления: эта задача требует плана. "
                        "Сначала вызови create_plan. Не выполняй другие действия до создания плана."
                    ),
                }
            )
            continue

        if action == "create_plan":
            plan_created = True

        reason = action_data.get("reason")

        debug_log("ACTION", action)

        debug_log("REASON", reason)

        result = execute_action(action_data)
        observation = str(result)

        WORK_ACTIONS = {
            "read_file",
            "write_file",
            "list_files",
            "run_command",
            "create_tool",
            "list_tools",
            "run_tool",
        }

        if plan_created and action in WORK_ACTIONS:
            plan_result = mark_next_step_done()
            observation += f"\n\nPlan update: {plan_result}"

        append_short_memory(
            "Agent Action",
            f"Action: {action}\nReason: {reason}\nResult:\n{result}",
        )

        if action == "read_file":
            file_was_read = True

        if action == "final_answer":
            unfinished_steps = get_unfinished_steps()

            if unfinished_steps:
                if len(unfinished_steps) == 1 and is_final_step(unfinished_steps[0][1]):
                    mark_next_step_done()
                else:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Ошибка управления: план ещё не завершён. "
                                "Сначала выполни следующий рабочий шаг плана."
                            ),
                        }
                    )
                    continue

            final_text = observation

            append_short_memory(
                "Final Answer",
                final_text,
            )

            clear_plan()

            return final_text

        debug_log("OBSERVATION", observation)

        messages.append(
            {
                "role": "assistant",
                "content": raw_response,
            }
        )

        messages.append(
            {
                "role": "user",
                "content": f"Observation:\n{observation}",
            }
        )

    return "Void остановился: достигнут лимит шагов."


def debug_log(title: str, value):
    if not DEBUG:
        return

    print(f"\n--- {title} ---")
    print(value)


def task_requires_plan(user_input: str) -> bool:
    keywords = [
        "проанализируй",
        "анализ",
        "статистику",
        "статистика",
        "посчитай",
        "найди",
        "проверь проект",
        "изучи проект",
        "составь отчёт",
        "отчет",
        "исследуй",
    ]

    text = user_input.lower()
    return any(keyword in text for keyword in keywords)


def task_requires_file_read(user_input: str) -> bool:
    text = user_input.lower()

    keywords = [
        "опиши файл",
        "объясни файл",
        "проанализируй файл",
        "что в файле",
        "actions.py",
        ".py",
        ".md",
        ".txt",
        ".json",
    ]

    return any(keyword in text for keyword in keywords)
