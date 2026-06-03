"""OpenAI-compatible LM Studio client."""

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam


client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",
)


def ask_llm(messages: list[ChatCompletionMessageParam]) -> str:
    response = client.chat.completions.create(
        model="local-model",
        messages=messages,
        temperature=0.1,
        max_tokens=1000,
    )
    return response.choices[0].message.content or ""

