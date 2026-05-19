from agent import run_agent


def main():
    print("Void v0.1")
    print("Напиши задачу. Для выхода: exit\n")

    while True:
        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit"]:
            print("Void stopped.")
            break

        try:
            result = run_agent(user_input)
            print("\nVoid:")
            print(result)
            print()
        except Exception as error:
            print("\nERROR:")
            print(error)
            print()


if __name__ == "__main__":
    main()
