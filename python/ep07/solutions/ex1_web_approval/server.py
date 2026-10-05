import json
from pathlib import Path

from agent import approvals, run_agent
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

app = FastAPI()
STATIC = Path(__file__).parent / "static"


def to_sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/ask")
def ask(question: str):
    def stream():
        try:
            for event in run_agent(question):
                yield to_sse(event)
        except Exception as err:
            yield to_sse({"type": "error", "content": f"에러: {err}"})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/approve/{approval_id}")
def approve(approval_id: str, ok: bool):
    box = approvals.get(approval_id)
    if box is None:
        raise HTTPException(404, "기다리는 승인 요청이 없습니다")
    box["ok"] = ok
    box["event"].set()
    return {"ok": ok}
