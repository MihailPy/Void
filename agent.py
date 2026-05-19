import json

from actions import answer, read_file, write_file, list_files
from llm import ask_chatgpt
from prompts import SYSTEM_PROMPT


def parse_llm_response(raw_response: str) -> dict:
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        raise ValueError(f"LLM вернула невалидный JSON:\n{raw_response}")


def execute_action(action_data: dict) -> str:
    action = action_data.get("action")
    arguments = action_data.get("arguments", {})

    if action == "answer":
        return answer(arguments.get("text", ""))

    if action == "read_file":
        return read_file(arguments["path"])

    if action == "write_file":
        return write_file(
            arguments["path"],
            arguments["content"],
        )

    if action == "list_files":
        return list_files(arguments.get("path", "."))

    return f"Неизвестное действие: {action}"


def run_agent(user_input: str) -> str:
    raw_response = ask_chatgpt(SYSTEM_PROMPT, user_input)

    print("\n--- RAW LLM RESPONSE ---")
    print(raw_response)

    action_data = parse_llm_response(raw_response)

    print("\n--- ACTION ---")
    print(action_data["action"])

    result = execute_action(action_data)

    return result
