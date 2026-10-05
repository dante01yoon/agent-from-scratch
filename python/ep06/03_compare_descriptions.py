import argparse
import os

from agent import BAD_TOOLS, GOOD_TOOLS
from evaluate import CASES, money, run_eval, summarize

parser = argparse.ArgumentParser()
parser.add_argument("--model", default=os.environ.get("MODEL"))
parser.add_argument("--repeats", type=int, default=3)
args = parser.parse_args()
if not args.model:
    parser.error("MODEL 환경변수나 --model이 필요합니다")

rows = []
for label, tools in [("나쁜 설명", BAD_TOOLS), ("좋은 설명", GOOD_TOOLS)]:
    print(f"\n[{label}] {args.model}, 케이스 {len(CASES)}개 × {args.repeats}번")
    rows.append((label, summarize(run_eval(args.model, args.repeats, tools))))

print("\n| 도구 설명 | 통과율 | 실제 청구액/회 | 가격표 추정/회 | 평균 도구 호출 |")
print("|---|---|---|---|---|")
for label, s in rows:
    print(
        f"| {label} | {s['passed']}/{s['runs']} ({s['pass_rate']:.0%}) "
        f"| {money(s['mean_billed'])} | {money(s['mean_cost'])} "
        f"| {s['mean_tools']:.1f} |"
    )
