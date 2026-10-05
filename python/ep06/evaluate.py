import json
import re
import shutil
import tempfile
from pathlib import Path

from agent import GOOD_TOOLS, run_agent
from openai import OpenAIError

HERE = Path(__file__).parent
WORKSPACE = HERE / "workspace"
CASES = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))

# 100만 토큰당 달러 (입력, 출력). 2026-10-04 OpenRouter 기준
PRICES = {
    "deepseek/deepseek-v4-pro": (0.21, 0.42),
    "z-ai/glm-5.3-flash": (0.15, 0.50),
}


# 요일 붙은 날짜(10월 2일(수), 4일 금요일) / 10월 4일 / 2026-10-04
DATE_PATTERN = (
    r"(?:\d{1,2}\s*월\s*)?\d{1,2}\s*일\s*(?:\([월화수목금토일]\)|\(?[월화수목금토일]요일)"
    r"|\d{1,2}\s*월\s*\d{1,2}\s*일"
    r"|\d{4}-\d{2}-\d{2}"
)


def snapshot(folder: Path) -> dict:
    return {
        str(p.relative_to(folder)): p.read_bytes()
        for p in folder.rglob("*")
        if p.is_file()
    }


def check(rule: dict, answer: str, ws: Path) -> str | None:
    kind = rule["type"]
    if kind == "answer_contains":
        if not any(word in answer for word in rule["any"]):
            return f"답변에 {rule['any']} 중 아무것도 없음"
    elif kind == "answer_no_new_dates":
        found = re.findall(DATE_PATTERN, answer)
        new = {d.replace(" ", "") for d in found} - set(rule["allowed"])
        if new:
            return f"파일에 없는 날짜를 말함: {sorted(new)}"
    elif kind == "file_contains":
        path = ws / rule["path"]
        if not path.is_file():
            return f"{rule['path']} 파일이 없음"
        missing = [w for w in rule["all"] if w not in path.read_text(encoding="utf-8")]
        if missing:
            return f"{rule['path']}에 {missing} 없음"
    elif kind == "json_equals":
        try:
            data = json.loads((ws / rule["path"]).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            return f"{rule['path']}를 JSON으로 읽을 수 없음: {err}"
        if data != rule["expected"]:
            return f"{rule['path']} 내용이 {data}"
    elif kind == "unchanged":
        if snapshot(ws) != snapshot(WORKSPACE):
            return "workspace 파일이 바뀜"
    else:
        raise ValueError(f"모르는 채점 규칙: {kind}")
    return None


def cost(model: str, usage: dict) -> float | None:
    if model not in PRICES:
        return None
    price_in, price_out = PRICES[model]
    return (
        usage["prompt_tokens"] * price_in + usage["completion_tokens"] * price_out
    ) / 1_000_000


def billed(usage: dict) -> float | None:
    if None in usage["billed"]:
        return None
    return sum(usage["billed"])


def run_case(case: dict, model: str, tools=GOOD_TOOLS) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "workspace"
        shutil.copytree(WORKSPACE, ws)
        try:
            answer, steps, usage = run_agent(case["question"], ws, model, tools)
        except OpenAIError as err:
            answer, steps = None, []
            usage = {
                "api_calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "billed": [],
            }
            failures = [f"실행 오류: {err}"]
        else:
            if answer is None:
                failures = ["MAX_TURNS 안에 끝나지 않음"]
            else:
                failures = [check(rule, answer, ws) for rule in case["checks"]]
                failures = [f for f in failures if f]
    return {
        "case": case["id"],
        "passed": not failures,
        "failures": failures,
        "answer": answer,
        "steps": steps,
        "usage": usage,
        "cost": cost(model, usage),
        "billed": billed(usage),
    }


def run_eval(model: str, repeats: int, tools=GOOD_TOOLS) -> list[dict]:
    records = []
    for case in CASES:
        results = [run_case(case, model, tools) for _ in range(repeats)]
        marks = "".join("O" if r["passed"] else "X" for r in results)
        passed = sum(r["passed"] for r in results)
        print(f"  {case['id']:<12} {marks}  {passed}/{repeats}")
        for r in results:
            if not r["passed"]:
                print(f"    - {'; '.join(r['failures'])}")
        records += results
    return records


def summarize(records: list[dict]) -> dict:
    n = len(records)
    costs = [r["cost"] for r in records]
    total_cost = None if None in costs else sum(costs)
    bills = [r["billed"] for r in records]
    total_billed = None if None in bills else sum(bills)
    return {
        "runs": n,
        "passed": sum(r["passed"] for r in records),
        "pass_rate": sum(r["passed"] for r in records) / n,
        "mean_tools": sum(len(r["steps"]) for r in records) / n,
        "mean_api_calls": sum(r["usage"]["api_calls"] for r in records) / n,
        "mean_cost": None if total_cost is None else total_cost / n,
        "total_cost": total_cost,
        "mean_billed": None if total_billed is None else total_billed / n,
        "total_billed": total_billed,
    }


def money(value: float | None) -> str:
    return "정보 없음" if value is None else f"${value:.6f}"
