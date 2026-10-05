import json
import os
import sys
import threading
import uuid
from pathlib import Path

from openai import OpenAI

client = OpenAI()
WORKSPACE = (Path(__file__).parent / "workspace").resolve()
MAX_TURNS = 10
APPROVAL_TIMEOUT = 300
NEEDS_APPROVAL = {"write_file"}
approvals = {}

tools = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "workspace 폴더 안의 모든 파일 경로를 한 줄에 하나씩 보여 준다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
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
            "description": "workspace 폴더 안에 파일을 쓴다. 이미 있으면 덮어쓴다. 사람이 승인해야 실행된다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "예: notes/port.md"},
                    "content": {"type": "string", "description": "파일에 쓸 내용"},
                },
                "required": ["path", "content"],
            },
        },
    },
]


def run_tool(name: str, args: dict) -> str:
    if name == "list_files":
        files = [
            p.relative_to(WORKSPACE).as_posix()
            for p in WORKSPACE.rglob("*")
            if p.is_file()
        ]
        return "\n".join(sorted(files))
    if name not in ("read_file", "write_file"):
        raise ValueError(f"없는 도구입니다: {name}")
    full = (WORKSPACE / args["path"]).resolve()
    if not full.is_relative_to(WORKSPACE):
        raise PermissionError("workspace 밖의 파일은 다룰 수 없습니다")
    if name == "read_file":
        return full.read_text(encoding="utf-8")
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(args["content"], encoding="utf-8")
    return f"저장했습니다: {args['path']}"


def wait_for_approval(approval_id: str) -> bool:
    box = approvals[approval_id]
    answered = box["event"].wait(timeout=APPROVAL_TIMEOUT)
    del approvals[approval_id]
    return answered and box["ok"]


def run_agent(question: str):
    messages = [{"role": "user", "content": question}]
    turn = 0

    while turn < MAX_TURNS:
        turn += 1
        yield {"type": "turn", "turn": turn}
        response = client.chat.completions.create(
            model=os.environ["MODEL"],
            tools=tools,
            messages=messages,
            extra_body={"provider": {"max_price": {"completion": 1}}},
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            yield {"type": "answer", "content": message.content}
            return

        for call in message.tool_calls:
            yield {
                "type": "tool_call",
                "name": call.function.name,
                "arguments": call.function.arguments,
            }
            approved = True
            if call.function.name in NEEDS_APPROVAL:
                approval_id = uuid.uuid4().hex
                approvals[approval_id] = {"event": threading.Event(), "ok": False}
                yield {
                    "type": "approval",
                    "id": approval_id,
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                }
                approved = wait_for_approval(approval_id)
            if not approved:
                result = "사용자가 승인하지 않았습니다"
            else:
                try:
                    result = run_tool(
                        call.function.name, json.loads(call.function.arguments)
                    )
                except Exception as err:
                    result = f"에러: {err}"
            yield {"type": "tool_result", "content": result}
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )

    yield {"type": "error", "content": f"{MAX_TURNS}회차 안에 끝내지 못했습니다"}


if __name__ == "__main__":
    question = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "README.md를 읽고 이 서버의 포트 번호를 알려줘"
    )
    for event in run_agent(question):
        print(event)
        if event["type"] == "approval":
            box = approvals[event["id"]]
            box["ok"] = input("승인할까요? (y/n) ").strip() == "y"
            box["event"].set()
