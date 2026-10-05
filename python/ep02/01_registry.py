import json
import os
import sys
from pathlib import Path

from openai import OpenAI

client = OpenAI()
WORKSPACE = (Path(__file__).parent / "workspace").resolve()
MAX_TURNS = 10


def safe_path(path: str) -> Path:
    full = (WORKSPACE / path).resolve()
    if not full.is_relative_to(WORKSPACE):
        raise PermissionError("workspace 밖의 경로는 다룰 수 없습니다")
    return full


def read_file(path: str) -> str:
    full = safe_path(path)
    if full.is_dir():
        raise IsADirectoryError(f"{path}는 폴더입니다. list_files로 안을 보세요")
    if not full.is_file():
        raise FileNotFoundError(f"{path} 파일이 없습니다. list_files로 확인하세요")
    lines = full.read_text(encoding="utf-8").splitlines()
    return "\n".join(f"{n}: {line}" for n, line in enumerate(lines, start=1))


def list_files(path: str = ".") -> str:
    base = safe_path(path)
    files = [
        p.relative_to(WORKSPACE).as_posix() for p in base.rglob("*") if p.is_file()
    ]
    return "\n".join(sorted(files)) or "(파일 없음)"


def write_file(path: str, content: str) -> str:
    full = safe_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return f"저장했습니다: {path} ({len(content.splitlines())}줄)"


TOOLS = {
    "read_file": {
        "function": read_file,
        "description": "workspace 안의 파일 내용을 읽는다. path는 workspace 기준 상대 경로다.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "예: README.md"}},
            "required": ["path"],
        },
    },
    "list_files": {
        "function": list_files,
        "description": "workspace 안의 파일 목록을 본다. path는 workspace 기준 상대 경로다.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "예: ."}},
        },
    },
    "write_file": {
        "function": write_file,
        "description": "workspace 안에 파일을 쓴다. path는 workspace 기준 상대 경로다.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "예: TODO.md"},
                "content": {"type": "string", "description": "파일에 쓸 내용"},
            },
            "required": ["path", "content"],
        },
    },
}

tools = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": spec["description"],
            "parameters": spec["parameters"],
        },
    }
    for name, spec in TOOLS.items()
]


def run_tool(name: str, args: dict) -> str:
    if name not in TOOLS:
        raise ValueError(f"없는 도구입니다: {name}")
    return TOOLS[name]["function"](**args)


question = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "workspace에 있는 TODO 주석을 모아서 TODO.md로 정리해줘"
)
messages = [{"role": "user", "content": question}]
turn = 0
tool_count = 0
error_count = 0

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
        print(f"[{turn}회차] {call.function.name}({call.function.arguments[:80]})")
        tool_count += 1
        try:
            result = run_tool(call.function.name, json.loads(call.function.arguments))
        except Exception as err:
            result = f"에러: {err}"
            error_count += 1
            print(f"    {result}")
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

print(f"\nAPI 호출 {turn}번 · 도구 호출 {tool_count}번 · 에러 {error_count}번")
