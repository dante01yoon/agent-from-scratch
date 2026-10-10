from agent import HERE, check, fresh_calendar, run_agent

root = fresh_calendar(HERE / "work")
for task in [
    "다음 주 화요일 오후 3시에 민수랑 1시간 '디자인 리뷰' 잡아줘",
    "다음 주 화요일 오후 3시 반에 민수랑 30분 '1:1' 잡아줘. 겹치면 바로 뒤로 잡아 줘",
]:
    print("요청:", task)
    result = run_agent(task, root, validate=True)
    print("답:", result["answer"], "\n")
print((root / "calendar.json").read_text(encoding="utf-8"))
print("규칙 검사:", check(root) or "문제 없음")
