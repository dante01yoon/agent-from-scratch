import argparse

from evaluate import CASES, PRICES, money, run_eval, summarize

parser = argparse.ArgumentParser()
parser.add_argument("--models", nargs="+", default=list(PRICES))
parser.add_argument("--repeats", type=int, default=3)
args = parser.parse_args()

rows = []
for model in args.models:
    print(f"\n[{model}] 케이스 {len(CASES)}개 × {args.repeats}번")
    rows.append((model, summarize(run_eval(model, args.repeats))))

print(
    "\n| 모델 | 통과율 | 실제 청구액/회 | 가격표 추정/회 | 평균 도구 호출 | 평균 API 호출 |"
)
print("|---|---|---|---|---|---|")
for model, s in rows:
    print(
        f"| {model} | {s['passed']}/{s['runs']} ({s['pass_rate']:.0%}) "
        f"| {money(s['mean_billed'])} | {money(s['mean_cost'])} "
        f"| {s['mean_tools']:.1f} | {s['mean_api_calls']:.1f} |"
    )
