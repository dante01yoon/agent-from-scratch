import subprocess
import sys
import tempfile
from pathlib import Path

from agent import SAMPLE, fresh_copy, run_agent

TASK = "테스트가 실패합니다. 고쳐 주세요."
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 1

# sample_project/calc.py에 심어 둔 버그와 원래 코드
BUGS = [
    {"name": "빼기 순서", "buggy": "return b - a", "fixed": "return a - b"},
    {
        "name": "0으로 나누기",
        "buggy": "return 0",
        "fixed": 'raise ZeroDivisionError("0으로 나눌 수 없습니다")',
    },
    {"name": "평균 분모", "buggy": "(len(numbers) - 1)", "fixed": "len(numbers)"},
]


def make_case(bug: dict, dest: Path) -> Path:
    root = fresh_copy(dest)
    calc = root / "calc.py"
    source = calc.read_text(encoding="utf-8")
    for other in BUGS:
        if other is not bug:
            source = source.replace(other["buggy"], other["fixed"])
    calc.write_text(source, encoding="utf-8")
    return root


def grade(root: Path) -> bool:
    tests = (root / "test_calc.py").read_text(encoding="utf-8")
    if tests != (SAMPLE / "test_calc.py").read_text(encoding="utf-8"):
        return False
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=root,
        capture_output=True,
        check=False,
        timeout=60,
    )
    return proc.returncode == 0


rows = []
for bug in BUGS:
    passed, turns, cost = 0, 0, 0.0
    for _ in range(RUNS):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_case(bug, Path(tmp) / "project")
            if grade(root):
                sys.exit(f"버그가 테스트에 잡히지 않습니다: {bug['name']}")
            result = run_agent(TASK, root, auto_approve=True)
            passed += grade(root)
            turns += result["turns"]
            cost += result["cost"]
    rows.append((bug["name"], passed, turns / RUNS, cost / RUNS))

print(f"\n{'버그':<10} {'통과':>6} {'평균 회차':>8} {'평균 비용':>10}")
for name, passed, turns, cost in rows:
    print(f"{name:<10} {passed:>3}/{RUNS:<2} {turns:>8.1f} {cost:>10.6f}")
total = sum(r[1] for r in rows)
print(f"전체 통과율: {total}/{len(BUGS) * RUNS}")
