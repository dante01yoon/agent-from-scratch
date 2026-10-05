import json
import os

from openai import OpenAI

client = OpenAI()
OMITTED = "(생략됨: 오래된 도구 결과입니다. 필요하면 다시 읽으세요)"

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "workspace 폴더 안의 파일 내용을 읽는다. path는 workspace 기준 상대 경로다.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    }
]


def request(call_id: str, path: str) -> dict:
    function = {"name": "read_file", "arguments": json.dumps({"path": path})}
    return {"id": call_id, "type": "function", "function": function}


# 1편 03_agent.py를 한 번 돌린 뒤의 대화 기록 모양 (예시)
messages = [
    {"role": "user", "content": "README.md를 읽고 이 서버의 포트 번호를 알려줘"},
    {"role": "assistant", "tool_calls": [request("call_1", "README.md")]},
    {"role": "tool", "tool_call_id": "call_1", "content": "# 주문 API 서버 ..."},
    {"role": "assistant", "tool_calls": [request("call_2", "config/server.json")]},
    {"role": "tool", "tool_call_id": "call_2", "content": '{"port": 4317}'},
    {"role": "assistant", "content": "포트 번호는 4317입니다."},
    {"role": "user", "content": "방금 찾은 포트 번호를 한 번 더 말해줘"},
]


def check_pairs(messages: list) -> str:
    waiting = set()
    for i, m in enumerate(messages):
        if m["role"] == "tool":
            if m["tool_call_id"] not in waiting:
                return f"{i}번 tool 메시지: 짝이 되는 요청서가 없습니다"
            waiting.remove(m["tool_call_id"])
            continue
        if waiting:
            return f"{i}번 메시지 앞: 결과를 못 받은 요청서 {sorted(waiting)}"
        waiting = {c["id"] for c in m.get("tool_calls", [])}
    if waiting:
        return f"마지막: 결과를 못 받은 요청서 {sorted(waiting)}"
    return "짝이 모두 맞습니다"


candidates = {
    "A. 최근 3개만 남기기": messages[-3:],
    "B. tool 메시지 지우기": [m for m in messages if m["role"] != "tool"],
    "C. tool 내용만 바꾸기": [
        {**m, "content": OMITTED} if m["role"] == "tool" else m for m in messages
    ],
}

for name, history in candidates.items():
    print(f"\n== {name}: {[m['role'] for m in history]}")
    print("검사:", check_pairs(history))
    try:
        response = client.chat.completions.create(
            model=os.environ["MODEL"],
            extra_body={"provider": {"max_price": {"completion": 1}}},
            tools=tools,
            messages=history,
        )
        print("API 응답:", response.choices[0].message.content)
    except Exception as err:
        print("API 에러:", err)
