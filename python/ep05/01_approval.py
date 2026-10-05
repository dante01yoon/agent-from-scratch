import json
import os
import sys
from pathlib import Path

from openai import OpenAI

client = OpenAI()
WORKSPACE = (Path(__file__).parent / "workspace").resolve()
MAX_TURNS = 10

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
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "workspace 폴더 안의 파일을 content로 통째로 덮어쓴다. 저장 전에 사용자가 승인해야 하며, 거절될 수 있다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "예: config/server.json"},
                    "content": {
                        "type": "string",
                        "description": "저장할 파일 전체 내용",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
]


def safe_path(path: str) -> Path:
    full = (WORKSPACE / path).resolve()
    if not full.is_relative_to(WORKSPACE):
        raise PermissionError("workspace 밖의 파일은 다룰 수 없습니다")
    return full


def ask(question: str) -> bool:
    return input(f"{question} [y/N] ").strip().lower() == "y"


def run_tool(name: str, args: dict) -> str:
    if name == "read_file":
        return safe_path(args["path"]).read_text(encoding="utf-8")
    if name == "write_file":
        full = safe_path(args["path"])
        print(f"----- {args['path']}에 저장할 내용 -----")
        print(args["content"])
        if not ask("이대로 저장할까요?"):
            return (
                "거절됨: 사용자가 저장을 승인하지 않았습니다. 파일은 바뀌지 않았습니다."
            )
        full.write_text(args["content"], encoding="utf-8")
        return f"저장했습니다: {args['path']}"
    raise ValueError(f"없는 도구입니다: {name}")


question = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "config/server.json의 timeoutMs를 10000으로 바꿔줘"
)
messages = [{"role": "user", "content": question}]
turn = 0

while turn < MAX_TURNS:
    turn += 1
    response = client.chat.completions.create(
        model=os.environ["MODEL"],
        tools=tools,
        messages=messages,
        extra_body={"provider": {"max_price": {"completion": 1}}},
    )
    message = response.choices[0].message
    messages.append(message.model_dump(exclude_none=True))

    if not message.tool_calls:
        print(message.content)
        break

    for call in message.tool_calls:
        print(f"[{turn}회차] {call.function.name}({call.function.arguments})")
        try:
            result = run_tool(call.function.name, json.loads(call.function.arguments))
        except Exception as err:
            result = f"에러: {err}"
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
