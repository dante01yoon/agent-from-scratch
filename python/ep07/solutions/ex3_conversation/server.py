import json
from pathlib import Path

from agent import run_agent
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse

app = FastAPI()
STATIC = Path(__file__).parent / "static"
sessions = {}


def to_sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/ask")
def ask(question: str, session: str):
    def stream():
        draft = list(sessions.get(session, []))
        try:
            for event in run_agent(question, draft):
                yield to_sse(event)
        except Exception as err:
            yield to_sse({"type": "error", "content": f"에러: {err}"})
            return
        sessions[session] = draft

    return StreamingResponse(stream(), media_type="text/event-stream")
