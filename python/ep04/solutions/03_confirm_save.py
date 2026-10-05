import json
import os
import sys
from pathlib import Path

from openai import OpenAI

client = OpenAI()
HERE = Path(__file__).parent
WORKSPACE = (HERE.parent / "workspace").resolve()
MEMORY = HERE / "data" / "memory_confirm.json"
MAX_TURNS = 10
SYSTEM = (
    "너는 workspace 폴더의 파일을 다루는 에이전트다. "
    "사용자가 선호나 오래 기억할 사실을 말하면 save_note로 저장해라. "
    "작업을 시작하기 전에 recall_notes로 저장된 메모를 확인하고 따르라."
)

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
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "다음 대화에서도 기억해야 할 사용자 선호나 사실을 한 문장으로 저장한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "예: 답변은 세 줄 이내"}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_notes",
            "description": "지금까지 저장한 메모를 모두 읽는다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def load_notes() -> list:
    if MEMORY.exists():
        return json.loads(MEMORY.read_text(encoding="utf-8"))
    return []


def run_tool(name: str, args: dict) -> str:
    if name == "read_file":
        full = (WORKSPACE / args["path"]).resolve()
        if not full.is_relative_to(WORKSPACE):
            raise PermissionError("workspace 밖의 파일은 읽을 수 없습니다")
        return full.read_text(encoding="utf-8")
    if name == "save_note":
        answer = input(f"\n메모 저장 요청: {args['text']}\n저장할까요? (y/n) ")
        if answer.strip().lower() != "y":
            return "사용자가 거절했습니다. 메모를 저장하지 않았습니다."
        notes = load_notes() + [args["text"]]
        MEMORY.parent.mkdir(exist_ok=True)
        text = json.dumps(notes, ensure_ascii=False, indent=2)
        MEMORY.write_text(text, encoding="utf-8")
        return f"저장했습니다 (메모 {len(notes)}개)"
    if name == "recall_notes":
        notes = load_notes()
        return "\n".join(f"- {n}" for n in notes) or "저장된 메모가 없습니다"
    raise ValueError(f"없는 도구입니다: {name}")


question = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "앞으로 답변은 항상 세 줄 이내로 짧게 해줘. 기억해 둬."
)
messages = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": question},
]
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
