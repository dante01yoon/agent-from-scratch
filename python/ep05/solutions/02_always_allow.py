import difflib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from openai import OpenAI

client = OpenAI()
WORKSPACE = (Path(__file__).parent.parent / "workspace").resolve()
MAX_TURNS = 10
ALLOWED = {"ls", "cat", "head", "wc", "grep"}
BLOCKED = {"rm", "sudo", "curl", "wget", "chmod", "chown", "mv", "dd", "kill"}
BLOCKED |= {"bash", "sh", "zsh"}
ALLOWED_MODULES = {"pytest"}
ALWAYS: set[str] = set()

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
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "workspace 폴더에서 터미널 명령 하나를 실행하고 출력을 돌려준다. 셸 기호(; | & > <)와 줄바꿈은 쓸 수 없고, python은 스크립트 파일 실행만 된다. 읽기 전용 명령(ls, cat, head, wc, grep)은 바로 실행되고, 그 밖의 명령은 사용자 승인이 필요하다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "예: ls config, python check_config.py",
                    }
                },
                "required": ["command"],
            },
        },
    },
]


def safe_path(path: str) -> Path:
    full = (WORKSPACE / path).resolve()
    if not full.is_relative_to(WORKSPACE):
        raise PermissionError("workspace 밖의 파일은 다룰 수 없습니다")
    return full


def ask(question: str, key: str) -> bool:
    if key in ALWAYS:
        print(f"(이번 세션 동안 항상 허용: {key})")
        return True
    answer = input(f"{question} [y/N/a=이번 세션 동안 항상] ").strip().lower()
    if answer == "a":
        ALWAYS.add(key)
    return answer in ("y", "a")


def show_diff(path: str, full: Path, new: str) -> None:
    old = full.read_text(encoding="utf-8") if full.exists() else ""
    diff = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile=f"{path} (지금)",
        tofile=f"{path} (바뀐 뒤)",
        lineterm="",
    )
    print("\n".join(diff) or "(바뀌는 내용 없음)")


def check_command(argv: list[str]) -> bool:
    if not argv:
        raise ValueError("빈 명령입니다")
    if argv[0] in BLOCKED:
        raise PermissionError(f"금지된 명령입니다: {argv[0]}")
    for arg in argv:
        if any(ch in arg for ch in ";|&><`$\n\r"):
            raise PermissionError(f"셸 기호나 줄바꿈은 쓸 수 없습니다: {arg!r}")
        if arg.startswith(("/", "~")) or ".." in Path(arg).parts:
            raise PermissionError(f"workspace 밖 경로는 쓸 수 없습니다: {arg}")
    if argv[0].startswith("python") and len(argv) > 1 and argv[1].startswith("-"):
        module = argv[2] if argv[1] == "-m" and len(argv) > 2 else None
        if module not in ALLOWED_MODULES:
            raise PermissionError(f"쓸 수 없는 python 옵션입니다: {argv[1]}")
    return argv[0] in ALLOWED


def run_command(command: str) -> str:
    argv = shlex.split(command)
    if not check_command(argv) and not ask(
        f"명령 실행 요청: {command}\n실행할까요?", " ".join(argv)
    ):
        reason = input("거절 이유 (없으면 Enter): ").strip() or "없음"
        return f"거절됨: 사용자가 명령 실행을 승인하지 않았습니다. 이유: {reason}"
    done = subprocess.run(
        argv,
        cwd=WORKSPACE,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return f"exit code {done.returncode}\n{done.stdout}{done.stderr}"[:2000]


def run_tool(name: str, args: dict) -> str:
    if name == "read_file":
        return safe_path(args["path"]).read_text(encoding="utf-8")
    if name == "write_file":
        full = safe_path(args["path"])
        show_diff(args["path"], full, args["content"])
        if not ask("이대로 저장할까요?", f"write_file {args['path']}"):
            reason = input("거절 이유 (없으면 Enter): ").strip() or "없음"
            return f"거절됨: 사용자가 저장을 승인하지 않았습니다. 파일은 바뀌지 않았습니다. 이유: {reason}"
        full.write_text(args["content"], encoding="utf-8")
        return f"저장했습니다: {args['path']}"
    if name == "run_command":
        return run_command(args["command"])
    raise ValueError(f"없는 도구입니다: {name}")


question = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "workspace에 어떤 파일이 있는지 보고, check_config.py로 설정을 검사해줘"
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
