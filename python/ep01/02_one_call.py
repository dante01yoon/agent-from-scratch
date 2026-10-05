import os

from openai import OpenAI

client = OpenAI()

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "workspace 폴더 안의 파일 내용을 읽는다. path는 workspace 기준 상대 경로다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "예: README.md"}
                },
                "required": ["path"],
            },
        },
    }
]

response = client.chat.completions.create(
    model=os.environ["MODEL"],
    tools=tools,
    messages=[
        {"role": "user", "content": "README.md를 읽고 이 서버의 포트 번호를 알려줘"},
    ],
)

choice = response.choices[0]
print("finish_reason:", choice.finish_reason)
print("content:", choice.message.content)
for call in choice.message.tool_calls or []:
    print("tool_call:", call.function.name, call.function.arguments)
