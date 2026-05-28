from agent import run_agent
from memory_manager import clear_short_memory


class Color:
    RESET = "\033[0m"

    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def print_header():
    print()
    print(f"{Color.BOLD}{Color.CYAN}Void v0.2{Color.RESET}")
    print(f"{Color.GRAY}Local AI assistant. Type /help for commands.{Color.RESET}")
    print(f"{Color.CYAN}/clear-memory{Color.RESET} очистить short-term memory")
    print()


def print_help():
    print()
    print(f"{Color.BOLD}Commands:{Color.RESET}")
    print(f"{Color.CYAN}/help{Color.RESET}   показать команды")
    print(f"{Color.CYAN}/exit{Color.RESET}   выйти")
    print(f"{Color.CYAN}/quit{Color.RESET}   выйти")
    print()


def print_response(text: str):
    print()
    print(f"{Color.BOLD}{Color.GREEN}Void:{Color.RESET}")
    print(text)
    print()


def print_error(error: Exception):
    print()
    print(f"{Color.BOLD}{Color.RED}ERROR:{Color.RESET}")
    print(f"{Color.RED}{error}{Color.RESET}")
    print()


class Color:
    RESET = "\033[0m"

    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def print_header():
    print()
    print(f"{Color.BOLD}{Color.CYAN}Void v0.2{Color.RESET}")
    print(f"{Color.GRAY}Local AI assistant. Type /help for commands.{Color.RESET}")
    print()


def print_help():
    print()
    print(f"{Color.BOLD}Commands:{Color.RESET}")
    print(f"{Color.CYAN}/help{Color.RESET}   показать команды")
    print(f"{Color.CYAN}/exit{Color.RESET}   выйти")
    print(f"{Color.CYAN}/quit{Color.RESET}   выйти")
    print()


def print_response(text: str):
    print()
    print(f"{Color.BOLD}{Color.GREEN}Void:{Color.RESET}")
    print(text)
    print()


def print_error(error: Exception):
    print()
    print(f"{Color.BOLD}{Color.RED}ERROR:{Color.RESET}")
    print(f"{Color.RED}{error}{Color.RESET}")
    print()


def main():
    print_header()

    while True:
        try:
            user_input = input(f"{Color.BOLD}{Color.BLUE}You:{Color.RESET} ").strip()

            if not user_input:
                continue

            if user_input in ["/exit", "/quit", "exit", "quit"]:
                print(f"{Color.GRAY}Void stopped.{Color.RESET}")
                break

            if user_input == "/help":
                print_help()
                continue

            if user_input == "/clear-memory":
                clear_short_memory()
                print(f"{Color.GRAY}Short-term memory cleared.{Color.RESET}")
                continue

            result = run_agent(user_input)
            print_response(result)

        except KeyboardInterrupt:
            print()
            print(f"{Color.GRAY}Void stopped.{Color.RESET}")
            break

        except Exception as error:
            print_error(error)


if __name__ == "__main__":
    main()
