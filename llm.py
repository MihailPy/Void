from openai import OpenAI


client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",  # любое значение, LM Studio обычно не проверяет ключ
)


def ask_chatgpt(system_prompt: str, user_input: str) -> str:
    response = client.chat.completions.create(
        model="local-model",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content
