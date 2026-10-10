"""traces/*.jsonl 기록을 브라우저 타임라인(timeline.html)으로 그린다.
한 줄 = 스팬 하나. 막대 위치는 시작 시각, 길이는 걸린 시간. 줄을 누르면 기록된 값이 펼쳐진다.
사용: uv run python 03_timeline.py [기록 파일 ...]   (없으면 traces 폴더의 모든 기록)
"""

import html
import json
import sys
from pathlib import Path

from tracer import load

SLOW_SEC = 5.0  # 이보다 오래 걸린 모델 호출은 노란 테두리
COLORS = {"invoke_agent": "#8f8c83", "chat": "#9cc4ff", "execute_tool": "#7fc97f"}
DANGER = ("deploy.env", "DEPLOY_CHECK.md")


def depth_of(span: dict, by_id: dict) -> int:
    d = 0
    while span["parent_id"]:
        span = by_id[span["parent_id"]]
        d += 1
    return d


def label(span: dict) -> str:
    a = span["attrs"]
    if span["name"] == "invoke_agent":
        return f"에이전트 실행 · 방어 {a.get('defense')}"
    if span["name"] == "chat":
        return (
            f"{a['turn']}회차 모델 호출 · 토큰 {a['input_tokens']}+{a['output_tokens']}"
        )
    shown = f"{a['turn']}회차 {a['tool']}({a.get('args', {}).get('path', '')})"
    return shown + (" → 거절" if a.get("result", "").startswith("거절") else "")


def is_danger(span: dict) -> bool:
    return span["attrs"].get("args", {}).get("path", "") in DANGER


def trace_html(path: Path) -> str:
    spans = load(path)
    by_id = {s["span_id"]: s for s in spans}
    run = next(s for s in spans if s["name"] == "invoke_agent")
    t0, total = run["start"], run["end"] - run["start"]
    rows = []
    for s in spans:
        left = 100 * (s["start"] - t0) / total
        width = max(0.4, 100 * (s["end"] - s["start"]) / total)
        color = "#e86a6a" if is_danger(s) else COLORS[s["name"]]
        slow = s["name"] == "chat" and s["end"] - s["start"] > SLOW_SEC
        outline = ";outline:2px solid #f2b84b;outline-offset:2px" if slow else ""
        detail = html.escape(json.dumps(s["attrs"], ensure_ascii=False, indent=1))
        rows.append(
            f'<details class="row"><summary>'
            f'<span class="name" style="padding-left:{depth_of(s, by_id) * 18}px">{html.escape(label(s))}</span>'
            f'<span class="track"><i style="left:{left:.2f}%;width:{width:.2f}%;background:{color}{outline}"></i></span>'
            f'<span class="sec">{s["end"] - s["start"]:.1f}초</span></summary><pre>{detail}</pre></details>'
        )
    a = run["attrs"]
    head = f"전체 {total:.1f}초 · 회차 {a.get('turns')} · 비용 ${a.get('cost', 0):.6f}"
    return f'<section><h2>{html.escape(path.name)}</h2><p class="sub">{head}</p>{"".join(rows)}</section>'


paths = [Path(p) for p in sys.argv[1:]] or sorted(Path("traces").glob("*.jsonl"))
page = f"""<!doctype html><meta charset="utf-8"><title>에이전트 행동 기록</title>
<style>
body{{background:#14161c;color:#e8e6df;font:16px/1.5 "Noto Sans KR",sans-serif;margin:0;padding:36px 56px}}
h1{{font-size:30px;margin:0}} h2{{font-size:20px;color:#f2b84b;margin:30px 0 2px}} .sub{{color:#9a988f;margin:0 0 10px}}
.row{{border-bottom:1px solid #23262f}}
summary{{display:grid;grid-template-columns:420px 1fr 70px;gap:14px;align-items:center;padding:5px 0;cursor:pointer;list-style:none}}
.track{{position:relative;height:16px;background:#1e212a;border-radius:4px}}
.track i{{position:absolute;top:0;height:100%;border-radius:4px}}
.sec{{font-family:"JetBrains Mono",monospace;text-align:right;color:#c8c4b8}}
pre{{background:#1b1e26;border-radius:8px;padding:12px;margin:4px 0 10px 0;font-size:13px;white-space:pre-wrap}}
.legend span{{margin-right:18px}} .legend i{{display:inline-block;width:14px;height:10px;border-radius:3px;margin-right:6px}}
</style>
<h1>에이전트 행동 기록</h1>
<p class="legend"><span><i style="background:#9cc4ff"></i>모델 호출 (chat)</span><span><i style="background:#7fc97f"></i>도구 실행 (execute_tool)</span><span><i style="background:#e86a6a"></i>비밀값 파일을 건드린 도구</span><span>줄을 누르면 기록된 값이 펼쳐집니다</span></p>
{"".join(trace_html(p) for p in paths)}
"""
Path("timeline.html").write_text(page, encoding="utf-8")
print(f"기록 {len(paths)}개 → timeline.html 을 브라우저로 여세요")
