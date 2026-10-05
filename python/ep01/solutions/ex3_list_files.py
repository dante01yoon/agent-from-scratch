import json
import os
import sys
from pathlib import Path

from openai import OpenAI

client = OpenAI()
WORKSPACE = (Path(__file__).parent.parent / "workspace").resolve()
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
            "name": "list_files",
            "description": "workspace 폴더 안의 모든 파일 경로를 workspace 기준 상대 경로로 보여 준다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def run_tool(name: str, args: dict) -> str:
    if name == "list_files":
        files = [p for p in WORKSPACE.rglob("*") if p.is_file()]
        return "\n".join(str(p.relative_to(WORKSPACE)) for p in sorted(files))
    if name != "read_file":
        raise ValueError(f"없는 도구입니다: {name}")
    full = (WORKSPACE / args["path"]).resolve()
    if not full.is_relative_to(WORKSPACE):
        raise PermissionError("workspace 밖의 파일은 읽을 수 없습니다")
    return full.read_text(encoding="utf-8")


question = sys.argv[1] if len(sys.argv) > 1 else "이 프로젝트의 서버 포트 번호를 알려줘"
messages = [{"role": "user", "content": question}]
turn = 0

while turn < MAX_TURNS:
    turn += 1
    response = client.chat.completions.create(
        model=os.environ["MODEL"],
        tools=tools,
        messages=messages,
    )
    message = response.choices[0].message
    messages.append(message.model_dump(exclude_none=True))

    if not message.tool_calls:
        print(message.content)
        break

    for call in message.tool_calls:
        print(f"[{turn}회차] {call.function.name}({call.function.arguments})")
        try:
            result = run_tool(
                call.function.name, json.loads(call.function.arguments or "{}")
            )
        except Exception as err:
            result = f"에러: {err}"
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
