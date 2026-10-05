import json
import os
import sys
from pathlib import Path

from openai import OpenAI

client = OpenAI()
HERE = Path(__file__).parent
WORKSPACE = (HERE / "workspace").resolve()
SESSION = HERE / "data" / "session.json"
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
                    "path": {"type": "string", "description": "예: logs/2026-10-03.log"}
                },
                "required": ["path"],
            },
        },
    }
]


def run_tool(name: str, args: dict) -> str:
    if name != "read_file":
        raise ValueError(f"없는 도구입니다: {name}")
    full = (WORKSPACE / args["path"]).resolve()
    if not full.is_relative_to(WORKSPACE):
        raise PermissionError("workspace 밖의 파일은 읽을 수 없습니다")
    return full.read_text(encoding="utf-8")


def load_session() -> list:
    if SESSION.exists():
        return json.loads(SESSION.read_text(encoding="utf-8"))
    return []


def save_session(messages: list) -> None:
    SESSION.parent.mkdir(exist_ok=True)
    text = json.dumps(messages, ensure_ascii=False, indent=2)
    SESSION.write_text(text, encoding="utf-8")


question = (
    sys.argv[1] if len(sys.argv) > 1 else "logs/2026-10-03.log를 읽고 에러를 정리해줘"
)
messages = load_session()
print(f"[세션] 이전 메시지 {len(messages)}개를 불러왔습니다")
messages.append({"role": "user", "content": question})
turn = 0

while turn < MAX_TURNS:
    turn += 1
    response = client.chat.completions.create(
        model=os.environ["MODEL"],
        extra_body={"provider": {"max_price": {"completion": 1}}},
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
            result = run_tool(call.function.name, json.loads(call.function.arguments))
        except Exception as err:
            result = f"에러: {err}"
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

save_session(messages)
print(f"[세션] 메시지 {len(messages)}개를 {SESSION.name}에 저장했습니다")
