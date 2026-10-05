import json
from pathlib import Path

from agent import run_agent
from fastapi import FastAPI
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
