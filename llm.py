from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam


client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",  # любое значение, LM Studio обычно не проверяет ключ
)


def ask_chatgpt(messages: list[ChatCompletionMessageParam]) -> str:
    response = client.chat.completions.create(
        model="local-model", messages=messages, temperature=0.2
    )

    return response.choices[0].message.content or ""
