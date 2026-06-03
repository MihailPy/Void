"""Deterministic routing for common Void requests."""

import re

from void.core.types import AgentAction, RouteResult


def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


class Router:
    """Simple regex/keyword router that avoids LLM calls for known tasks."""

    def route(self, user_input: str) -> RouteResult:
        text = user_input.strip()
        lowered = text.lower()

        remember_match = re.match(
            r"^(?:запомни|remember)\s*[:：]\s*(.+)$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if remember_match:
            return RouteResult(
                matched=True,
                confidence=0.95,
                action=AgentAction(
                    action="remember_fact",
                    arguments={"fact": _clean(remember_match.group(1))},
                    reason="User explicitly asked to remember a fact.",
                ),
            )

        project_update_match = re.match(
            r"^(?:обнови память проекта|update project memory)\s*[:：]\s*(.+)$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if project_update_match:
            return RouteResult(
                matched=True,
                confidence=0.95,
                action=AgentAction(
                    action="update_project",
                    arguments={"content": _clean(project_update_match.group(1))},
                    reason="User explicitly asked to update project memory.",
                ),
            )

        if any(phrase in lowered for phrase in ("что ты помнишь", "какие факты", "что запомнено")):
            return RouteResult(
                matched=True,
                confidence=0.9,
                action=AgentAction(
                    "read_facts",
                    {},
                    "User asks to read remembered facts.",
                ),
            )

        if any(
            phrase in lowered
            for phrase in ("что реализовано", "состояние проекта", "что дальше", "память проекта")
        ):
            return RouteResult(
                matched=True,
                confidence=0.85,
                action=AgentAction("read_project", {}, "User asks for project memory."),
            )

        if any(
            phrase in lowered
            for phrase in (
                "статистика проекта",
                "статистику проекта",
                "сколько файлов",
                "какие файлы в проекте",
                "сделай статистику проекта",
            )
        ):
            return RouteResult(
                matched=True,
                confidence=0.9,
                action=AgentAction(
                    "project_stats",
                    {"path": "."},
                    "User asks for project statistics.",
                ),
            )

        read_match = re.search(
            r"(?:прочитай файл|покажи файл|read file)\s+(.+)$",
            text,
            re.IGNORECASE,
        )
        if read_match:
            return RouteResult(
                matched=True,
                confidence=0.9,
                action=AgentAction(
                    "read_file",
                    {"path": _clean(read_match.group(1))},
                    "User asks to read a specific file.",
                ),
            )

        list_match = re.search(
            r"(?:покажи файлы в|список файлов в|list files in)\s+(.+)$",
            text,
            re.IGNORECASE,
        )
        if list_match:
            return RouteResult(
                matched=True,
                confidence=0.85,
                action=AgentAction(
                    "list_files",
                    {"path": _clean(list_match.group(1))},
                    "User asks to list a directory.",
                ),
            )

        if any(
            phrase in lowered
            for phrase in (
                "запрос на добавление функции",
                "добавление функции",
                "новая возможность",
                "новую возможность",
                "request capability",
            )
        ):
            name = "requested_capability"
            if "сетев" in lowered:
                name = "network_requests"
            return RouteResult(
                matched=True,
                confidence=0.88,
                action=AgentAction(
                    "request_capability",
                    {
                        "name": name,
                        "problem": text,
                        "why_self_tool_not_enough": (
                            "Existing safe built-in tools do not provide this capability."
                        ),
                        "suggested_function_signature": f"{name}(...) -> ToolResult",
                        "suggested_behavior": (
                            "Implement the capability as a safe, registered built-in tool "
                            "with bounded inputs and clear errors."
                        ),
                        "usage_example": text,
                    },
                    "User asks to request a new capability.",
                ),
            )

        return RouteResult(matched=False, confidence=0.0)
