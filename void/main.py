"""Void command-line interface."""

from void.core.agent import Agent
from void.core.types import AgentAction
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
    print(f"{Color.BOLD}{Color.CYAN}Void v0.3{Color.RESET}")
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


def main() -> None:
    registry = build_registry()
    agent = Agent(registry=registry, debug=DEBUG)

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
                result = registry.execute(AgentAction("clear_session", {}, "CLI command."))
                print_response(result.content)
                continue
            if user_input == "/clear-facts":
                result = registry.execute(AgentAction("clear_facts", {}, "CLI command."))
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
