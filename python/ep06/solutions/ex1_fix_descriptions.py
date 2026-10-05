import argparse
import json
import os
from pathlib import Path

from agent import GOOD_TOOLS, tool
from evaluate import CASES, money, run_eval, summarize

IMPROVED_TOOLS = [
    tool(
        "read_file",
        "workspace 폴더 안의 파일 내용을 읽는다. path는 workspace 기준 상대 경로다. "
        "답에 필요한 값은 짐작하지 말고 이 도구로 파일에서 직접 확인한다. "
        "에러가 돌아오면 그 파일은 없는 것이니, 내용을 지어내지 말고 없다고 답한다.",
        {"path": {"type": "string", "description": "예: config/server.json"}},
        ["path"],
    ),
    tool(
        "list_files",
        "폴더 안의 모든 파일 경로를 하위 폴더까지 한 줄에 하나씩 돌려준다. "
        "어떤 파일이 있는지 모를 때 먼저 쓴다. 여러 파일을 세거나 모아야 하면 "
        "여기 나온 파일을 빠짐없이 read_file로 읽은 뒤에 답한다.",
        {"path": {"type": "string", "description": "workspace 기준 폴더. 전체는 ."}},
        ["path"],
    ),
    tool(
        "write_file",
        "파일 전체를 content로 덮어쓴다. 파일이 없으면 만든다. "
        "기존 파일을 고칠 때는 먼저 read_file로 읽고, 바꿀 부분만 바꾼 전체 내용을 넣는다. "
        "content에서 빠진 내용은 지워지므로 나머지 값을 그대로 옮겨 적는다.",
        {
            "path": {"type": "string", "description": "workspace 기준 상대 경로"},
            "content": {"type": "string", "description": "저장할 전체 내용"},
        },
        ["path", "content"],
    ),
]


def show_failures(model: str) -> None:
    path = Path(__file__).parent.parent / "results" / f"{model.replace('/', '_')}.json"
    if not path.exists():
        print(f"{path.name}이 없습니다. 01_run_eval.py를 먼저 실행하세요.")
        return
    failed = [
        r for r in json.loads(path.read_text(encoding="utf-8")) if not r["passed"]
    ]
    print(f"실패한 실행 {len(failed)}개 ({path.name})")
    for r in failed:
        print(f"\n[{r['case']}] {'; '.join(r['failures'])}")
        print(f"  답: {r['answer']}")
        for step in r["steps"]:
            print(f"  - {step}")


parser = argparse.ArgumentParser()
parser.add_argument("--model", default=os.environ.get("MODEL"))
parser.add_argument("--repeats", type=int, default=3)
args = parser.parse_args()
if not args.model:
    parser.error("MODEL 환경변수나 --model이 필요합니다")

show_failures(args.model)

rows = []
for label, tools in [("고치기 전", GOOD_TOOLS), ("고친 뒤", IMPROVED_TOOLS)]:
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
