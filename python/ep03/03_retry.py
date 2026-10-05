import json
import os
import sys
from collections import Counter

from common import SCHEMAS, TOOL_ERRORS, cost_usd, run_tool
from openai import APIConnectionError, APIStatusError, OpenAI

client = OpenAI(max_retries=3, timeout=60)
MODEL = os.environ["MODEL"]
MAX_TURNS = 10
MAX_COST_USD = float(os.environ.get("MAX_COST_USD", "0.01"))
REPEAT_LIMIT = 3

seen = Counter()


def handle(call) -> str:
    name = call.function.name
    try:
        args = json.loads(call.function.arguments or "{}")
    except json.JSONDecodeError as err:
        return (
            f"에러: 인자가 올바른 JSON이 아닙니다 ({err}). JSON 객체로 다시 보내세요."
        )

    key = (name, json.dumps(args, sort_keys=True, ensure_ascii=False))
    seen[key] += 1
    if seen[key] >= REPEAT_LIMIT:
        return (
            f"에러: 같은 호출을 {seen[key]}번째 반복했습니다. 결과는 바뀌지 않습니다. "
            "다른 방법을 쓰거나 지금까지 알아낸 내용으로 답하세요."
        )

    try:
        return run_tool(name, args)
    except TOOL_ERRORS as err:
        return f"에러: {err}"


question = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "README.md를 읽고 이 서버의 포트 번호를 알려줘"
)
messages = [{"role": "user", "content": question}]
total_cost = 0.0
turn = 0

while True:
    if turn >= MAX_TURNS:
        print(f"[중단] 최대 반복 {MAX_TURNS}회에 닿았습니다")
        break
    if total_cost >= MAX_COST_USD:
        print(f"[중단] 비용 상한 ${MAX_COST_USD}에 닿았습니다")
        break
    turn += 1

    try:
        response = client.chat.completions.create(
            model=MODEL,
            tools=SCHEMAS,
            messages=messages,
        )
    except APIStatusError as err:
        print(f"[중단] API 오류: {err.message}")
        break
    except APIConnectionError as err:
        print(f"[중단] 연결 실패: {err}")
        break
    total_cost += cost_usd(MODEL, response.usage)
    message = response.choices[0].message
    messages.append(message.model_dump(exclude_none=True))

    if not message.tool_calls:
        print(message.content)
        break

    for call in message.tool_calls:
        result = handle(call)
        print(f"[{turn}회차] {call.function.name}({call.function.arguments})")
        if result.startswith("에러:"):
            print(f"  → {result}")
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

print(f"합계: 호출 {turn}번 · ${total_cost:.6f}")
