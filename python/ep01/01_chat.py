import os

from openai import OpenAI

client = OpenAI()

response = client.chat.completions.create(
    model=os.environ["MODEL"],
    messages=[
        {"role": "user", "content": "README.md를 읽고 이 서버의 포트 번호를 알려줘"},
    ],
)

print(response.choices[0].message.content)
