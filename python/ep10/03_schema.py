import json

from agent import Event, run_cases

# Pydantic 모델에서 만든 JSON 스키마. 손으로 쓴 스키마에는 없던 규칙(형식, 최솟값·최댓값)이 들어 있다
print(json.dumps(Event.model_json_schema()["properties"], ensure_ascii=False, indent=1))
run_cases(validate=True, schema="pydantic", title="스키마까지 Pydantic으로 만든 캘린더")
