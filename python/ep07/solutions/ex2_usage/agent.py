import json
import os
import sys
from pathlib import Path

from openai import OpenAI

client = OpenAI()
WORKSPACE = (Path(__file__).parent / "workspace").resolve()
MAX_TURNS = 10
# 100만 토큰당 달러 (입력, 출력). OpenRouter 2026-10-04 기준
PRICES = {
    "deepseek/deepseek-v4-pro": (0.21, 0.42),
    "z-ai/glm-5.3-flash": (0.15, 0.50),
}

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
]


def run_tool(name: str, args: dict) -> str:
    if name == "list_files":
        files = [
            p.relative_to(WORKSPACE).as_posix()
            for p in WORKSPACE.rglob("*")
            if p.is_file()
        ]
        return "\n".join(sorted(files))
    if name != "read_file":
        raise ValueError(f"없는 도구입니다: {name}")
    full = (WORKSPACE / args["path"]).resolve()
    if not full.is_relative_to(WORKSPACE):
        raise PermissionError("workspace 밖의 파일은 읽을 수 없습니다")
    return full.read_text(encoding="utf-8")


def usage_event(usage) -> dict:
    prices = PRICES.get(os.environ["MODEL"])
    cost = None
    if prices:
        price_in, price_out = prices
        cost = (
            usage.prompt_tokens * price_in + usage.completion_tokens * price_out
        ) / 1_000_000
    return {
        "type": "usage",
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "cost": cost,
        "billed": (usage.model_extra or {}).get("cost"),
    }


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
        if response.usage:
            yield usage_event(response.usage)
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
