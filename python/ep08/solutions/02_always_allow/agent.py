import difflib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from openai import OpenAI

client = OpenAI()
MODEL = os.environ["MODEL"]
HERE = Path(__file__).parent
SAMPLE = HERE / "sample_project"

MAX_TURNS = 15
MAX_COST_USD = 0.05
TEST_TIMEOUT = 60
MAX_OUTPUT = 2000
KEEP_RESULTS = 3

# 100만 토큰당 (입력, 출력) 달러. 다른 모델을 쓰면 여기에 추가한다
PRICES = {
    "deepseek/deepseek-v4-pro": (0.21, 0.42),
    "z-ai/glm-5.3-flash": (0.15, 0.50),
}

SYSTEM = """너는 작은 코딩 에이전트다. 작업 폴더의 Python 프로젝트에서 실패하는 테스트를 고친다.
1. run_tests로 무엇이 실패하는지 확인한다
2. read_file로 관련 코드를 읽는다
3. write_file로 코드를 고친다. 테스트 파일은 고치지 않는다
4. run_tests로 다시 확인한다. 모두 통과하면 무엇을 왜 바꿨는지 짧게 보고한다"""


def fresh_copy(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        SAMPLE, dest, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache")
    )
    return dest.resolve()


def safe_path(root: Path, path: str) -> Path:
    full = (root / path).resolve()
    if not full.is_relative_to(root):
        raise PermissionError("작업 폴더 밖은 접근할 수 없습니다")
    return full


def list_files(root: Path) -> str:
    names = []
    for p in sorted(root.rglob("*")):
        parts = p.relative_to(root).parts
        if p.is_file() and not any(
            x.startswith(".") or x == "__pycache__" for x in parts
        ):
            names.append("/".join(parts))
    return "\n".join(names) or "(빈 폴더)"


def read_file(root: Path, path: str) -> str:
    return safe_path(root, path).read_text(encoding="utf-8")


def write_file(root: Path, path: str, content: str) -> str:
    full = safe_path(root, path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return f"{path} 저장 완료 ({len(content)}자)"


def run_tests(root: Path) -> str:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
            timeout=TEST_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"에러: 테스트가 {TEST_TIMEOUT}초 안에 끝나지 않았습니다"
    output = proc.stdout + proc.stderr
    if len(output) > MAX_OUTPUT:
        output = "(앞부분 생략)\n" + output[-MAX_OUTPUT:]
    return f"exit code: {proc.returncode}\n{output}"


TOOLS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "run_tests": run_tests,
}


def tool(name: str, description: str, properties: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
            },
        },
    }


PATH = {"type": "string", "description": "작업 폴더 기준 상대 경로. 예: calc.py"}
SCHEMAS = [
    tool("list_files", "작업 폴더의 파일 목록을 돌려준다.", {}),
    tool("read_file", "파일 내용을 읽는다.", {"path": PATH}),
    tool(
        "write_file",
        "파일 전체를 content로 덮어쓴다. 사용자가 diff를 보고 승인해야 저장된다.",
        {
            "path": PATH,
            "content": {"type": "string", "description": "새 파일 전체 내용"},
        },
    ),
    tool("run_tests", "pytest로 테스트를 돌리고 exit code와 출력을 돌려준다.", {}),
]


def make_diff(root: Path, path: str, content: str) -> str:
    full = safe_path(root, path)
    old = full.read_text(encoding="utf-8") if full.exists() else ""
    lines = difflib.unified_diff(
        old.splitlines(keepends=True),
        content.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(lines) or "(바뀌는 내용 없음)"


def ask_human(diff: str) -> str:
    print(diff)
    try:
        answer = input("이 변경을 적용할까요? [y/N/a=이번 세션 동안 항상 허용] ")
    except EOFError:
        answer = ""
    return answer.strip().lower()


def run_tool(root: Path, name: str, args: dict, session: dict) -> str:
    if name not in TOOLS:
        raise ValueError(f"없는 도구입니다: {name}")
    if name == "write_file":
        if session["always_allow"]:
            print(f"(이번 세션 항상 허용) {args['path']}")
        else:
            answer = ask_human(make_diff(root, args["path"], args["content"]))
            if answer == "a":
                session["always_allow"] = True
            elif answer != "y":
                return "사용자가 이 변경을 거절했습니다. 파일은 바뀌지 않았습니다."
    return TOOLS[name](root, **args)


def trim_old_results(messages: list) -> None:
    results = [m for m in messages if m["role"] == "tool"]
    for m in results[:-KEEP_RESULTS]:
        m["content"] = "(생략됨: 오래된 도구 결과)"


def run_agent(task: str, root: Path, auto_approve: bool = False) -> dict:
    price_in, price_out = PRICES[MODEL]
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": task},
    ]
    cost = 0.0
    session = {"always_allow": auto_approve}

    for turn in range(1, MAX_TURNS + 1):
        trim_old_results(messages)
        response = client.chat.completions.create(
            model=MODEL,
            tools=SCHEMAS,
            messages=messages,
            extra_body={"provider": {"max_price": {"completion": 1}}},
        )
        usage = response.usage
        if usage and (usage.model_extra or {}).get("cost") is not None:
            cost += usage.model_extra["cost"]
        elif usage:
            cost += usage.prompt_tokens * price_in / 1_000_000
            cost += usage.completion_tokens * price_out / 1_000_000
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            return {"answer": message.content, "turns": turn, "cost": cost}
        if cost > MAX_COST_USD:
            return {"answer": "중단: 비용 상한 초과", "turns": turn, "cost": cost}

        for call in message.tool_calls:
            print(f"[{turn}회차] {call.function.name}({call.function.arguments[:80]})")
            try:
                args = json.loads(call.function.arguments or "{}")
                result = run_tool(root, call.function.name, args, session)
            except Exception as err:
                result = f"에러: {err}"
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )

    return {"answer": "중단: 최대 반복 횟수 도달", "turns": MAX_TURNS, "cost": cost}


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "테스트가 실패합니다. 고쳐 주세요."
    root = fresh_copy(HERE / "work")
    print(f"작업 폴더: {root}")
    result = run_agent(task, root)
    print(result["answer"])
    print(f"회차 {result['turns']} · 비용 ${result['cost']:.6f}")
