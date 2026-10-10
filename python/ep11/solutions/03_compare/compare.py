"""기록 두 개를 나란히 비교한다. 사용: uv run python compare.py <기록 A> <기록 B>"""

import sys
from pathlib import Path

from tracer import load


def facts(path: Path) -> dict:
    spans = load(path)
    run = next(s for s in spans if s["name"] == "invoke_agent")
    tools = [s for s in spans if s["name"] == "execute_tool"]
    chats = [s for s in spans if s["name"] == "chat"]
    return {
        "방어": run["attrs"].get("defense"),
        "전체 시간(초)": round(run["end"] - run["start"], 1),
        "회차": run["attrs"].get("turns"),
        "비용($)": round(run["attrs"].get("cost", 0), 6),
        "입력 토큰 합": sum(s["attrs"]["input_tokens"] for s in chats),
        "도구 호출 수": len(tools),
        "거절된 도구": sum(
            s["attrs"].get("result", "").startswith("거절") for s in tools
        ),
        "도구 순서": " → ".join(s["attrs"]["tool"] for s in tools),
    }


a, b = (facts(Path(p)) for p in sys.argv[1:3])
print(f"항목 | {Path(sys.argv[1]).name} | {Path(sys.argv[2]).name}")
for key in a:
    mark = "" if a[key] == b[key] else "  ← 다름"
    print(f"{key} | {a[key]} | {b[key]}{mark}")
