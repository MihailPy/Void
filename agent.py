import json

from openai.types.chat import ChatCompletionMessageParam

from actions import read_file, run_command, write_file, list_files
from llm import ask_chatgpt
from prompts import SYSTEM_PROMPT


MAX_STEPS = 6


def parse_llm_response(raw_response: str) -> dict:
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        raise ValueError(f"LLM вернула невалидный JSON:\n{raw_response}")


def execute_action(action_data: dict):
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

    return f"Неизвестное действие: {action}"


def run_agent(user_input: str) -> str:
    messages: list[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_input,
        },
    ]

    for step in range(1, MAX_STEPS + 1):
        print(f"\n--- STEP {step} ---")

        raw_response = ask_chatgpt(messages)

        print("\n--- RAW LLM RESPONSE ---")
        print(raw_response)

        action_data = parse_llm_response(raw_response)

        action = action_data.get("action")
        reason = action_data.get("reason")

        print("\n--- ACTION ---")
        print(action)

        print("\n--- REASON ---")
        print(reason)

        result = execute_action(action_data)

        if action == "final_answer":
            return str(result)

        observation = str(result)

        print("\n--- OBSERVATION ---")
        print(observation)

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
