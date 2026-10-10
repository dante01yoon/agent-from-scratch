from agent import HERE, check, fresh_calendar, run_agent

root = fresh_calendar(HERE / "work")
task = "다음 주 월요일 오후 5시 반에 지영이랑 1시간 '회식 장소 정하기' 잡아줘. 규칙에 안 맞으면 알아서 맞춰 줘"
result = run_agent(task, root, validate=True)
print("답:", result["answer"])
print((root / "calendar.json").read_text(encoding="utf-8"))
print("규칙 검사:", check(root) or "문제 없음")
