"""에이전트 행동 기록기. 스팬(시작·끝이 있는 작업 하나)을 JSONL 파일에 한 줄씩 남긴다.

스팬 이름은 OpenTelemetry GenAI 관례를 따른다.
  invoke_agent  에이전트 실행 전체 (가장 바깥)
  chat          모델 호출 한 번
  execute_tool  도구 실행 한 번
"""

import json
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class Tracer:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.trace_id = uuid.uuid4().hex[:16]
        self.stack = []  # 지금 열려 있는 스팬들. 마지막 것이 부모가 된다

    @contextmanager
    def span(self, name: str, **attrs):
        span = {
            "trace_id": self.trace_id,
            "span_id": uuid.uuid4().hex[:8],
            "parent_id": self.stack[-1]["span_id"] if self.stack else None,
            "name": name,
            "start": time.time(),
            "attrs": attrs,
        }
        self.stack.append(span)
        try:
            yield span["attrs"]  # with 블록 안에서 토큰·결과 같은 값을 채운다
        except Exception as err:
            span["attrs"]["error"] = str(err)
            raise
        finally:
            self.stack.pop()
            span["end"] = time.time()
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(span, ensure_ascii=False) + "\n")


class NoTracer:
    """기록하지 않을 때 쓰는 빈 기록기. run_agent 코드를 바꾸지 않아도 된다."""

    @contextmanager
    def span(self, name: str, **attrs):
        yield attrs


def load(path: Path) -> list[dict]:
    spans = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return sorted(spans, key=lambda s: s["start"])
