import csv
import json
import os
import sys
import time
from pathlib import Path

from common import SCHEMAS, TOOL_ERRORS, cost_usd, run_tool
from openai import OpenAI

client = OpenAI()
MODEL = os.environ["MODEL"]
MAX_TURNS = 10
LOG_PATH = Path(__file__).parent / "usage_log.csv"

run_id = time.strftime("%Y-%m-%d %H:%M:%S")
is_new = not LOG_PATH.exists()
log_file = LOG_PATH.open("a", newline="", encoding="utf-8-sig", buffering=1)
writer = csv.writer(log_file)
if is_new:
    writer.writerow(["실행", "모델", "회차", "입력 토큰", "출력 토큰", "비용(USD)"])

question = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "README.md를 읽고 이 서버의 포트 번호를 알려줘"
)
messages = [{"role": "user", "content": question}]
total_in = total_out = 0
total_cost = 0.0
turn = 0

while turn < MAX_TURNS:
    turn += 1
    response = client.chat.completions.create(
        model=MODEL,
        tools=SCHEMAS,
        messages=messages,
    )
    usage = response.usage
    cost = cost_usd(MODEL, usage)
    total_in += usage.prompt_tokens
    total_out += usage.completion_tokens
    total_cost += cost
    print(
        f"[{turn}회차] 입력 {usage.prompt_tokens:,} · 출력 {usage.completion_tokens:,} 토큰"
        f" · ${cost:.6f}"
    )
    writer.writerow(
        [
            run_id,
            MODEL,
            turn,
            usage.prompt_tokens,
            usage.completion_tokens,
            f"{cost:.6f}",
        ]
    )

    message = response.choices[0].message
    messages.append(message.model_dump(exclude_none=True))

    if not message.tool_calls:
        print(message.content)
        break

    for call in message.tool_calls:
        print(f"  {call.function.name}({call.function.arguments})")
        try:
            result = run_tool(call.function.name, json.loads(call.function.arguments))
        except TOOL_ERRORS as err:
            result = f"에러: {err}"
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

print(
    f"합계: 호출 {turn}번 · 입력 {total_in:,} · 출력 {total_out:,} 토큰 · ${total_cost:.6f}"
)
log_file.close()
print(f"기록: {LOG_PATH.name}")
