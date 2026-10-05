import json
import os
import sys
from pathlib import Path

from openai import OpenAI

client = OpenAI()
WORKSPACE = (Path(__file__).parent / "workspace").resolve()
MAX_TURNS = 10
MAX_CHARS = 2000


def safe_path(path: str) -> Path:
    full = (WORKSPACE / path).resolve()
    if not full.is_relative_to(WORKSPACE):
        raise PermissionError("workspace 밖의 경로는 다룰 수 없습니다")
    return full


def read_file(path: str, start_line: int = 1) -> str:
    full = safe_path(path)
    if full.is_dir():
        raise IsADirectoryError(f"{path}는 폴더입니다. list_files로 안을 보세요")
    if not full.is_file():
        raise FileNotFoundError(f"{path} 파일이 없습니다. list_files로 확인하세요")
    lines = full.read_text(encoding="utf-8").splitlines()
    if not 1 <= start_line <= max(len(lines), 1):
        raise ValueError(f"start_line은 1~{len(lines)} 사이여야 합니다")
    numbered = [f"{n}: {line}" for n, line in enumerate(lines, start=1)]
    result = "\n".join(numbered[start_line - 1 :])
    if len(result) <= MAX_CHARS:
        return result
    shown = result[:MAX_CHARS].rsplit("\n", 1)[0]
    next_line = start_line + shown.count("\n") + 1
    skipped = len(result) - len(shown)
    return f"{shown}\n(… {skipped:,}자 생략. 이어 읽기: start_line={next_line})"


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
        "description": (
            "workspace 안의 텍스트 파일 하나를 읽는다. "
            "결과는 한 줄마다 '줄번호: 내용' 형식이다. "
            f"결과가 {MAX_CHARS}자를 넘으면 잘리고 끝에 다음 start_line이 안내된다. "
            "경로를 모르면 먼저 list_files로 확인한다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "workspace 기준 상대 경로. 예: orders/service.py",
                },
                "start_line": {
                    "type": "integer",
                    "description": "몇 번째 줄부터 읽을지. 생략하면 1. 예: 41",
                },
            },
            "required": ["path"],
        },
    },
    "list_files": {
        "function": list_files,
        "description": (
            "workspace 안의 파일을 하위 폴더까지 전부 나열한다. "
            "결과는 한 줄에 경로 하나다. "
            "어떤 파일이 있는지 모를 때 가장 먼저 쓴다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "살펴볼 폴더. 생략하면 workspace 전체. 예: orders",
                }
            },
        },
    },
    "write_file": {
        "function": write_file,
        "description": (
            "workspace 안에 파일을 만들거나 덮어쓴다. "
            "기존 내용은 모두 지워지고 content로 바뀐다. "
            "여러 항목을 쓸 때는 내용을 다 모은 뒤 한 번에 호출한다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "workspace 기준 상대 경로. 예: TODO.md",
                },
                "content": {"type": "string", "description": "파일 전체 내용"},
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
