import argparse
import html
import json
import tempfile
from pathlib import Path

import agent
from agent import CASES, check, fresh_calendar, run_agent
from view import STYLE, week_html

MODES = {
    "none": ("검증 없음", False, "hand"),
    "validate": ("Pydantic 검증", True, "hand"),
    "schema": ("검증 + 스키마 자동 생성", True, "pydantic"),
}

parser = argparse.ArgumentParser()
parser.add_argument("--runs", type=int, default=3)
parser.add_argument(
    "--report-only", action="store_true", help="results.json으로 리포트만 다시 만든다"
)
args = parser.parse_args()


def is_error(call: dict) -> bool:
    return call["tool"] == "add_event" and call["result"].startswith("에러")


def measure() -> list[dict]:
    rows = []
    for mode, (label, validate, schema) in MODES.items():
        for i in range(args.runs):
            root = fresh_calendar(Path(tempfile.mkdtemp()) / "calendar")
            rejected = fixed = 0
            for case in CASES:
                before = len(json.loads((root / "calendar.json").read_text("utf-8")))
                out = run_agent(case["task"], root, validate, schema, quiet=True)
                errors = sum(is_error(c) for c in out["calls"])
                saved = (
                    len(json.loads((root / "calendar.json").read_text("utf-8")))
                    > before
                )
                rejected += errors
                fixed += errors > 0 and saved  # 거절당한 뒤 고쳐서 등록했다
            events = json.loads((root / "calendar.json").read_text("utf-8"))
            rows.append(
                {
                    "mode": mode,
                    "saved": len(events),
                    "bad": len(check(root)),
                    "rejected": rejected,
                    "fixed": fixed,
                    "events": events,
                }
            )
            r = rows[-1]
            print(
                f"{label} {i + 1}/{args.runs}: 저장 {r['saved']} · 규칙 위반 {r['bad']}"
                f" · 거절 {r['rejected']} · 스스로 고침 {r['fixed']}"
            )
    return rows


if args.report_only:  # 측정은 건너뛰고 저장된 결과로 리포트만 다시 만든다
    rows = json.loads(Path("results.json").read_text())
    args.runs = sum(r["mode"] == "none" for r in rows)
else:
    rows = measure()
    Path("results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))


# ---------- 브라우저로 볼 리포트 ----------
def total(mode: str, key: str) -> int:
    return sum(r[key] for r in rows if r["mode"] == mode)


table = "".join(
    f"<tr><td>{label}</td><td>{total(m, 'saved')}</td><td class='bad'>{total(m, 'bad')}</td>"
    f"<td>{total(m, 'rejected')}</td><td class='ok'>{total(m, 'fixed')}</td></tr>"
    for m, (label, _, _) in MODES.items()
)
calendars = "".join(
    f"<h2>{label} · 첫 번째 실행의 캘린더</h2>"
    + week_html(next(r for r in rows if r["mode"] == m)["events"])
    for m, (label, _, _) in MODES.items()
)
page = f"""<!doctype html><meta charset="utf-8"><title>도구 인자 검증 리포트</title>
<style>{STYLE}
table{{border-collapse:collapse;margin-top:16px;font-size:19px}}
td,th{{padding:8px 22px;border-bottom:1px solid #2a2e38;text-align:right}}
td:first-child,th:first-child{{text-align:left}} .bad{{color:#ffb3a3}} .ok{{color:#a9e0a9}}
</style>
<h1>잘못된 일정이 조용히 저장될까?</h1>
<p class="sub">요청 {len(CASES)}개를 방식마다 {args.runs}번씩 · 모델 {html.escape(agent.MODEL)} · 오늘은 {agent.TODAY}</p>
<table><tr><th>방식</th><th>저장된 일정</th><th>규칙 위반 저장</th><th>거절</th><th>스스로 고침</th></tr>{table}</table>
{calendars}
"""
Path("report.html").write_text(page, encoding="utf-8")
print("\n리포트: report.html 을 브라우저로 여세요")
