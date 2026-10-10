import sys
from pathlib import Path

from tracer import load

# 사용: uv run python 02_summary.py traces/<파일>.jsonl   (없으면 가장 최근 기록)
traces = sorted(Path("traces").glob("*.jsonl"))
path = Path(sys.argv[1]) if len(sys.argv) > 1 else traces[-1]
spans = load(path)
run = next(s for s in spans if s["name"] == "invoke_agent")
total = run["end"] - run["start"]

print(
    f"{path.name} · 전체 {total:.1f}초 · 회차 {run['attrs']['turns']} · 비용 ${run['attrs']['cost']:.6f}\n"
)
print("회차 | 모델 응답 | 입력 토큰 | 출력 토큰 | 비용 | 부른 도구")
for s in spans:
    if s["name"] == "chat":
        a = s["attrs"]
        tools = ", ".join(a["tool_calls"]) or "(답변)"
        print(
            f"{a['turn']:>4} | {s['end'] - s['start']:6.1f}초 | {a['input_tokens']:>8} | "
            f"{a['output_tokens']:>8} | ${a['cost']:.6f} | {tools}"
        )

slow = max(spans[1:], key=lambda s: s["end"] - s["start"])
pricey = max(
    (s for s in spans if s["name"] == "chat"), key=lambda s: s["attrs"]["cost"]
)
model_time = sum(s["end"] - s["start"] for s in spans if s["name"] == "chat")
print(
    f"\n가장 오래 걸린 스팬: {slow['name']} {slow['attrs'].get('turn')}회차 {slow['end'] - slow['start']:.1f}초"
)
print(f"가장 비싼 회차: {pricey['attrs']['turn']}회차 ${pricey['attrs']['cost']:.6f}")
print(f"전체 시간 중 모델을 기다린 비율: {model_time / total:.0%}")
