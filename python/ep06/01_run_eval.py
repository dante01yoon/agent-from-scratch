import argparse
import json
import os
from pathlib import Path

from evaluate import CASES, money, run_eval, summarize

parser = argparse.ArgumentParser()
parser.add_argument("--model", default=os.environ.get("MODEL"))
parser.add_argument("--repeats", type=int, default=3)
args = parser.parse_args()
if not args.model:
    parser.error("MODEL 환경변수나 --model이 필요합니다")

print(f"모델: {args.model}")
print(f"케이스 {len(CASES)}개 × {args.repeats}번 = {len(CASES) * args.repeats}번 실행")
records = run_eval(args.model, args.repeats)
s = summarize(records)

print(f"\n통과율: {s['passed']}/{s['runs']} ({s['pass_rate']:.0%})")
print(
    f"평균 도구 호출: {s['mean_tools']:.1f}회 / 평균 API 호출: {s['mean_api_calls']:.1f}회"
)
print(
    f"평균 비용: 실제 청구액 {money(s['mean_billed'])}/회 "
    f"(가격표 추정 {money(s['mean_cost'])})"
)
print(
    f"전체 비용: 실제 청구액 {money(s['total_billed'])} "
    f"(가격표 추정 {money(s['total_cost'])})"
)

out = Path(__file__).parent / "results" / f"{args.model.replace('/', '_')}.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"실행 기록: results/{out.name}")
