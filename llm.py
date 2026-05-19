import os
from openai import OpenAI


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def ask_chatgpt(system_prompt: str, user_input: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Не найден OPENAI_API_KEY в переменных окружения")

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content
