import json
import os
from pathlib import Path

from openai import OpenAI

client = OpenAI()
MAX_TURNS = 10


def tool(name, description, properties, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


GOOD_TOOLS = [
    tool(
        "read_file",
        "workspace 폴더 안의 파일 내용을 읽는다. path는 workspace 기준 상대 경로다.",
        {"path": {"type": "string", "description": "예: config/server.json"}},
        ["path"],
    ),
    tool(
        "list_files",
        "폴더 안의 모든 파일 경로를 한 줄에 하나씩 돌려준다. 어떤 파일이 있는지 모를 때 먼저 쓴다.",
        {"path": {"type": "string", "description": "workspace 기준 폴더. 전체는 ."}},
        ["path"],
    ),
    tool(
        "write_file",
        "파일 전체를 content로 덮어쓴다. 파일이 없으면 만든다. 일부만 고칠 때도 전체 내용을 넣는다.",
        {
            "path": {"type": "string", "description": "workspace 기준 상대 경로"},
            "content": {"type": "string", "description": "저장할 전체 내용"},
        },
        ["path", "content"],
    ),
]

BAD_TOOLS = [
    tool("read_file", "파일", {"path": {"type": "string"}}, ["path"]),
    tool("list_files", "목록", {"path": {"type": "string"}}, ["path"]),
    tool(
        "write_file",
        "쓰기",
        {"path": {"type": "string"}, "content": {"type": "string"}},
        ["path", "content"],
    ),
]


def safe_path(workspace: Path, path: str) -> Path:
    full = (workspace / path).resolve()
    if not full.is_relative_to(workspace):
        raise PermissionError("workspace 밖의 파일은 다룰 수 없습니다")
    return full


def run_tool(workspace: Path, name: str, args: dict) -> str:
    if name == "read_file":
        return safe_path(workspace, args["path"]).read_text(encoding="utf-8")
    if name == "list_files":
        folder = safe_path(workspace, args.get("path", "."))
        if not folder.is_dir():
            raise FileNotFoundError(f"폴더가 없습니다: {args.get('path')}")
        files = sorted(p for p in folder.rglob("*") if p.is_file())
        return "\n".join(str(p.relative_to(workspace)) for p in files)
    if name == "write_file":
        full = safe_path(workspace, args["path"])
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(args["content"], encoding="utf-8")
        return f"저장했습니다: {args['path']}"
    raise ValueError(f"없는 도구입니다: {name}")


def run_agent(question, workspace, model=None, tools=GOOD_TOOLS):
    workspace = Path(workspace).resolve()
    messages = [{"role": "user", "content": question}]
    steps = []
    usage = {"api_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "billed": []}
    turn = 0

    while turn < MAX_TURNS:
        turn += 1
        response = client.chat.completions.create(
            model=model or os.environ["MODEL"],
            tools=tools,
            messages=messages,
            extra_body={"provider": {"max_price": {"completion": 1}}},
        )
        usage["api_calls"] += 1
        if response.usage:
            usage["prompt_tokens"] += response.usage.prompt_tokens
            usage["completion_tokens"] += response.usage.completion_tokens
        billed = response.usage and (response.usage.model_extra or {}).get("cost")
        usage["billed"].append(billed)
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            return message.content or "", steps, usage

        for call in message.tool_calls:
            try:
                args = json.loads(call.function.arguments)
                result = run_tool(workspace, call.function.name, args)
            except (OSError, ValueError, KeyError, TypeError) as err:
                result = f"에러: {err}"
            steps.append(f"{call.function.name}({call.function.arguments})")
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )

    return None, steps, usage
