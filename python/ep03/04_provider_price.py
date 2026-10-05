import json
import os
import sys

from common import SCHEMAS, TOOL_ERRORS, billed_usd, cost_usd, run_tool
from openai import OpenAI

client = OpenAI()
MODEL = os.environ["MODEL"]
MAX_TURNS = 10
# 출력 100만 토큰당 $1보다 비싼 제공자로는 보내지 않는다 (OpenRouter provider.max_price)
CHEAP_ONLY = {"provider": {"max_price": {"completion": 1}}}

question = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "README.md를 읽고 이 서버의 포트 번호를 알려줘"
)


def run(extra_body: dict | None) -> tuple:
    messages = [{"role": "user", "content": question}]
    estimated = billed = 0.0
    turn = 0

    while turn < MAX_TURNS:
        turn += 1
        response = client.chat.completions.create(
            model=MODEL,
            tools=SCHEMAS,
            messages=messages,
            extra_body=extra_body,
        )
        provider = (response.model_extra or {}).get("provider", "?")
        cost = cost_usd(MODEL, response.usage)
        real = billed_usd(response.usage)
        estimated += cost
        billed += real or 0.0
        real_text = "없음" if real is None else f"${real:.6f}"
        print(f"[{turn}회차] {provider} · 추정 ${cost:.6f} · 청구 {real_text}")

        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        if not message.tool_calls:
            break

        for call in message.tool_calls:
            try:
                args = json.loads(call.function.arguments)
                result = run_tool(call.function.name, args)
            except TOOL_ERRORS as err:
                result = f"에러: {err}"
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )

    return turn, estimated, billed


print("=== 기본 라우팅")
before = run(None)
print("=== max_price 적용")
after = run(CHEAP_ONLY)

for label, (turns, estimated, billed) in (("기본", before), ("max_price", after)):
    print(f"{label}: 호출 {turns}번 · 추정 ${estimated:.6f} · 청구 ${billed:.6f}")
