from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam


client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",
)


def ask_chatgpt(messages: list[ChatCompletionMessageParam]) -> str:
    response = client.chat.completions.create(
        model="local-model",
        messages=messages,
        temperature=0.2,
    )

    content = response.choices[0].message.content

    if content is None:
        return ""

    return content
