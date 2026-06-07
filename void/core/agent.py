"""Single-action agent runtime for Void."""

import json
import re
from dataclasses import asdict
from typing import Any

from openai.types.chat import ChatCompletionMessageParam

from void.core.llm import ask_llm
from void.core.registry import ToolRegistry
from void.core.router import Router
from void.core.types import AgentAction, RouteResult, ToolResult
from void.prompts import SYSTEM_PROMPT
from void.tools.memory_tools import append_session, read_facts, read_project

DIRECT_ROUTE_CONFIDENCE = 0.85
MAX_JSON_RETRIES = 2


def extract_json(text: str) -> str:
    """Extract the first JSON object from an LLM response."""
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if not match:
        raise ValueError("JSON not found in LLM response.")
    return match.group(0)


def parse_action(raw_response: str) -> AgentAction:
    json_text = extract_json(raw_response)
    payload: dict[str, Any] = json.loads(json_text)

    action = payload.get("action")
    arguments = payload.get("arguments", {})
    reason = payload.get("reason", "")

    if not isinstance(action, str) or not action:
        raise ValueError("LLM response has no valid action.")
    if not isinstance(arguments, dict):
        raise ValueError("LLM response arguments must be an object.")
    if not isinstance(reason, str):
        reason = str(reason)

    return AgentAction(action=action, arguments=arguments, reason=reason)


class Agent:
    """Stable one-request, one-action runtime."""

    def __init__(
        self,
        registry: ToolRegistry,
        router: Router | None = None,
        debug: bool = False,
    ) -> None:
        self.registry = registry
        self.router = router or Router()
        self.debug = debug

    def handle(self, user_input: str) -> str:
        append_session("User Request", user_input)

        route = self.router.route(user_input)
        if self.debug:
            self._debug("route result", route)

        if (
            route.matched
            and route.confidence >= DIRECT_ROUTE_CONFIDENCE
            and route.action is not None
        ):
            result = self.registry.execute(route.action)
            if self.debug:
                self._debug("action", route.action)
                self._debug("tool result", result)
            self._save_result("Routed Action", route.action, result)
            return result.content

        action_or_error = self._ask_for_action(user_input)
        if isinstance(action_or_error, str):
            append_session("LLM Error", action_or_error)
            return action_or_error

        action = action_or_error
        result = self.registry.execute(action)

        if self.debug:
            self._debug("action", action)
            self._debug("tool result", result)

        self._save_result("LLM Action", action, result)
        return result.content

    def _ask_for_action(self, user_input: str) -> AgentAction | str:
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"FACTS MEMORY:\n{read_facts().content}"},
            {"role": "user", "content": f"PROJECT MEMORY:\n{read_project().content}"},
            {"role": "user", "content": user_input},
        ]

        for attempt in range(MAX_JSON_RETRIES + 1):
            try:
                raw_response = ask_llm(messages)
            except Exception as error:
                return f"Void could not reach the local LLM fallback: {error}"

            if self.debug:
                self._debug("raw llm response", raw_response)

            try:
                return parse_action(raw_response)
            except (json.JSONDecodeError, ValueError) as error:
                if attempt >= MAX_JSON_RETRIES:
                    return (
                        "Void could not parse the model response as a valid action JSON. "
                        f"Last error: {error}"
                    )
                messages.append({"role": "assistant", "content": raw_response})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous response was invalid. Return only valid JSON "
                            "in this format: "
                            '{"action": "...", "arguments": {}, "reason": "..."}'
                        ),
                    }
                )

        return "Void could not obtain a valid action from the model."

    def _save_result(self, title: str, action: AgentAction, result: ToolResult) -> None:
        append_session(
            title,
            (
                f"Action: {action.action}\n"
                f"Reason: {action.reason}\n"
                f"OK: {result.ok}\n"
                f"Terminal: {result.terminal}\n\n"
                f"{result.content}"
            ),
        )

    def _debug(self, title: str, value: object) -> None:
        print(f"\n--- {title.upper()} ---")
        if isinstance(value, (AgentAction, RouteResult, ToolResult)):
            print(asdict(value))
        else:
            print(value)
