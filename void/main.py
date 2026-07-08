"""Void command-line interface."""

import json

from void.__version__ import __version__
from void.core.agent import Agent
from void.core.capabilities import list_capabilities
from void.core.permissions import approve, clear_approval, list_approvals, reject
from void.core.types import AgentAction
from void.skills import build_skill_registry
from void.tools.builtin import build_registry

DEBUG = False


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def print_header() -> None:
    print()
    print(f"{Color.BOLD}{Color.CYAN}Void v{__version__}{Color.RESET}")
    print(f"{Color.GRAY}Local AI assistant. Type /help for commands.{Color.RESET}")
    print()


def print_help() -> None:
    print()
    print(f"{Color.BOLD}Commands:{Color.RESET}")
    print(f"{Color.CYAN}/help{Color.RESET}          show commands")
    print(f"{Color.CYAN}/exit{Color.RESET}          exit")
    print(f"{Color.CYAN}/quit{Color.RESET}          exit")
    print(f"{Color.CYAN}/clear-session{Color.RESET} clear session memory")
    print(f"{Color.CYAN}/clear-facts{Color.RESET}   clear facts memory")
    print(f"{Color.CYAN}/skills{Color.RESET}        show available skills")
    print(f"{Color.CYAN}/approvals{Color.RESET}     show pending approvals")
    print(f"{Color.CYAN}/activity{Color.RESET}      show recent activity")
    print(f"{Color.CYAN}/last-activity{Color.RESET} show latest activity")
    print(f"{Color.CYAN}/replay{Color.RESET}        replay last supported action")
    print(f"{Color.CYAN}/tasks{Color.RESET}         show scheduled tasks")
    print(f"{Color.CYAN}/capabilities{Color.RESET}  show all capabilities")
    print(f"{Color.CYAN}/requested{Color.RESET}     show requested capabilities")
    print(f"{Color.CYAN}/installed{Color.RESET}     show installed capabilities")
    print(f"{Color.CYAN}/rejected{Color.RESET}      show rejected capabilities")
    print(f"{Color.CYAN}/approve <id>{Color.RESET}  approve and run action")
    print(f"{Color.CYAN}/reject <id>{Color.RESET}   reject pending action")
    print(f"{Color.CYAN}/run-task <id>{Color.RESET} run scheduled task")
    print(f"{Color.CYAN}/enable-task <id>{Color.RESET} enable scheduled task")
    print(f"{Color.CYAN}/disable-task <id>{Color.RESET} disable scheduled task")
    print(f"{Color.CYAN}/delete-task <id>{Color.RESET} delete scheduled task")
    print()


def print_response(text: str) -> None:
    print()
    print(f"{Color.BOLD}{Color.GREEN}Void:{Color.RESET}")
    print(text)
    print()


def print_error(error: Exception) -> None:
    print()
    print(f"{Color.BOLD}{Color.RED}ERROR:{Color.RESET}")
    print(f"{Color.RED}{error}{Color.RESET}")
    print()


def print_skills(agent: Agent) -> None:
    print()
    print(f"{Color.BOLD}Skills:{Color.RESET}")
    for skill in agent.skill_registry.list_skills():
        print(f"{Color.CYAN}{skill.name}{Color.RESET}")
        print(f"  {skill.description}")
        print(f"  keywords: {', '.join(skill.keywords)}")
    print()


def print_approvals() -> None:
    approvals = list_approvals()
    print()
    print(f"{Color.BOLD}Pending approvals:{Color.RESET}")
    if not approvals:
        print("None.")
        print()
        return

    for approval in approvals:
        arguments = json.dumps(
            approval.get("arguments", {}),
            ensure_ascii=False,
            sort_keys=True,
        )
        print(
            f"{Color.CYAN}{approval.get('id', '')}{Color.RESET} {approval.get('action', '')}"
        )
        print(f"  reason: {approval.get('reason', '')}")
        if approval.get("category") or approval.get("risk_level"):
            print(
                "  metadata: "
                f"category={approval.get('category', 'unknown')}, "
                f"risk_level={approval.get('risk_level', 'unknown')}"
            )
        print(f"  arguments: {arguments}")
        print(f"  created_at: {approval.get('created_at', '')}")
    print()


def _capability_line(record: dict) -> str:
    name = record.get("name", "unknown")
    record_id = record.get("id", "")
    description = record.get("description", "")
    reason = record.get("reason")
    suffix = f" ({record_id})" if record_id else ""
    line = f"- {name}{suffix}"
    if description:
        line += f": {description}"
    if reason:
        line += f" [reason: {reason}]"
    return line


def print_capabilities(section: str | None = None) -> None:
    capabilities = list_capabilities()
    sections = {
        "installed": "Installed",
        "requested": "Requested",
        "rejected": "Rejected",
    }
    keys = [section] if section else list(sections.keys())

    print()
    for key in keys:
        print(f"{Color.BOLD}{sections[key]}:{Color.RESET}")
        records = capabilities[key]
        if not records:
            print("- None")
        else:
            for record in records:
                print(_capability_line(record))
        print()


def main() -> None:
    registry = build_registry()
    skill_registry = build_skill_registry()
    agent = Agent(registry=registry, skill_registry=skill_registry, debug=DEBUG)

    print_header()
    while True:
        try:
            user_input = input(f"{Color.BOLD}{Color.BLUE}You:{Color.RESET} ").strip()

            if not user_input:
                continue
            if user_input in {"/exit", "/quit", "exit", "quit"}:
                print(f"{Color.GRAY}Void stopped.{Color.RESET}")
                break
            if user_input == "/help":
                print_help()
                continue
            if user_input == "/clear-session":
                result = registry.execute(
                    AgentAction("clear_session", {}, "CLI command.")
                )
                print_response(result.content)
                continue
            if user_input == "/clear-facts":
                result = registry.execute(
                    AgentAction("clear_facts", {}, "CLI command.")
                )
                print_response(result.content)
                continue
            if user_input == "/skills":
                print_skills(agent)
                continue
            if user_input == "/approvals":
                print_approvals()
                continue
            if user_input == "/activity":
                result = registry.execute(
                    AgentAction("list_recent_activity", {}, "CLI command.")
                )
                print_response(result.content)
                continue
            if user_input == "/last-activity":
                result = registry.execute(
                    AgentAction("get_last_activity", {}, "CLI command.")
                )
                print_response(result.content)
                continue
            if user_input == "/replay":
                result = registry.execute(
                    AgentAction("repeat_last_activity", {}, "CLI command.")
                )
                print_response(result.content)
                continue
            if user_input == "/tasks":
                result = registry.execute(
                    AgentAction("list_scheduled_tasks", {}, "CLI command.")
                )
                print_response(result.content)
                continue
            if user_input == "/capabilities":
                print_capabilities()
                continue
            if user_input == "/requested":
                print_capabilities("requested")
                continue
            if user_input == "/installed":
                print_capabilities("installed")
                continue
            if user_input == "/rejected":
                print_capabilities("rejected")
                continue
            if user_input.startswith("/approve "):
                approval_id = user_input.removeprefix("/approve ").strip()
                action = approve(approval_id)
                if action is None:
                    print_response(f"Approval not found: {approval_id}")
                    continue

                result = registry.execute(action, bypass_confirmation=True)
                clear_approval(approval_id)
                print_response(result.content)
                continue
            if user_input.startswith("/reject "):
                approval_id = user_input.removeprefix("/reject ").strip()
                if reject(approval_id):
                    print_response("Approval rejected.")
                else:
                    print_response(f"Approval not found: {approval_id}")
                continue
            if user_input.startswith("/run-task "):
                task_id = user_input.removeprefix("/run-task ").strip()
                result = registry.execute(
                    AgentAction(
                        "run_scheduled_task",
                        {"task_id": task_id},
                        "CLI command.",
                    )
                )
                print_response(result.content)
                continue
            if user_input.startswith("/enable-task "):
                task_id = user_input.removeprefix("/enable-task ").strip()
                result = registry.execute(
                    AgentAction(
                        "enable_scheduled_task",
                        {"task_id": task_id},
                        "CLI command.",
                    )
                )
                print_response(result.content)
                continue
            if user_input.startswith("/disable-task "):
                task_id = user_input.removeprefix("/disable-task ").strip()
                result = registry.execute(
                    AgentAction(
                        "disable_scheduled_task",
                        {"task_id": task_id},
                        "CLI command.",
                    )
                )
                print_response(result.content)
                continue
            if user_input.startswith("/delete-task "):
                task_id = user_input.removeprefix("/delete-task ").strip()
                result = registry.execute(
                    AgentAction(
                        "delete_scheduled_task",
                        {"task_id": task_id},
                        "CLI command.",
                    )
                )
                print_response(result.content)
                continue

            print_response(agent.handle(user_input))

        except (KeyboardInterrupt, EOFError):
            print()
            print(f"{Color.GRAY}Void stopped.{Color.RESET}")
            break
        except Exception as error:
            print_error(error)


if __name__ == "__main__":
    main()
