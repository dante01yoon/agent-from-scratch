"""실패를 일부러 만들어 내는 가짜 모델 서버 (실습용, localhost 전용).

질문에 들어 있는 낱말로 상황을 고른다:
  "깨진 JSON" / "없는 도구" / "빌드"(같은 호출 반복) / "끝없이"(최대 반복)
  "500" / "429" (처음 몇 번만 실패) / "다운" (계속 실패)
"""

import json
import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()


def tool_call(n: int, name: str, args) -> dict:
    if not isinstance(args, str):
        args = json.dumps(args, ensure_ascii=False)
    return {
        "id": f"call_{n}",
        "type": "function",
        "function": {"name": name, "arguments": args},
    }


def reply(body: dict, content: str | None = None, calls: list | None = None) -> dict:
    sent = json.dumps(body["messages"] + body.get("tools", []), ensure_ascii=False)
    prompt_tokens = len(sent) // 3
    completion_tokens = 30 if calls else 60
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return {
        "id": "fake",
        "object": "chat.completion",
        "created": 0,
        "model": body["model"],
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if calls else "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def error(status: int, headers: dict | None = None) -> JSONResponse:
    content = {"error": {"message": f"가짜 서버가 일부러 낸 {status} 오류"}}
    return JSONResponse(content, status_code=status, headers=headers)


@app.post("/api/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    question = body["messages"][0]["content"]
    results = [m["content"] for m in body["messages"] if m["role"] == "tool"]
    n = len(results)
    retry = int(request.headers.get("x-stainless-retry-count", "0"))

    if "다운" in question:
        return error(503)
    if "500" in question and n == 0 and retry < 2:
        return error(500)
    if "429" in question and n == 0 and retry < 1:
        return error(429, {"retry-after": "1"})

    if "깨진 JSON" in question and n == 0:
        return reply(body, calls=[tool_call(n, "read_file", '{"path": "README.md"')])
    if "없는 도구" in question and n == 0:
        return reply(body, calls=[tool_call(n, "delete_file", {"path": "README.md"})])
    if "빌드" in question:
        if any(r.startswith("에러: 같은 호출") for r in results):
            return reply(
                body,
                content="(가짜 서버) 빌드가 아직 진행 중이라 결과를 알 수 없습니다.",
            )
        return reply(
            body, calls=[tool_call(n, "read_file", {"path": "jobs/build_status.txt"})]
        )
    if "끝없이" in question:
        return reply(
            body, calls=[tool_call(n, "read_file", {"path": f"page{n + 1}.txt"})]
        )

    # 과제 3: README 결과가 "(생략됨)"으로 줄어 있어도 이미 읽은 것으로 친다
    if not any("config/server.json" in r or r == "(생략됨)" for r in results):
        return reply(body, calls=[tool_call(n, "read_file", {"path": "README.md"})])
    if not any('"port"' in r for r in results):
        return reply(
            body, calls=[tool_call(n, "read_file", {"path": "config/server.json"})]
        )
    port = json.loads(results[-1])["port"]
    return reply(body, content=f"(가짜 서버) 포트는 {port}입니다.")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "5003")))
