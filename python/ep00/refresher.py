"""0편: 이 시리즈에서 자주 쓰는 Python 문법을 한 파일에 모았다.

실행: uv run python refresher.py
"""

import json
from pathlib import Path

# 1. dict와 list: 모델과 주고받는 대화(messages)는 dict들의 list다
messages = [{"role": "user", "content": "안녕"}]
messages.append({"role": "assistant", "content": "안녕하세요!"})
print(len(messages), messages[-1]["content"])

# 2. JSON 글자 <-> dict: 모델이 보내는 도구 인자는 JSON 글자로 온다
args = json.loads('{"path": "README.md"}')
print(args["path"])
print(json.dumps({"port": 4317}))


# 3. 함수와 f-string
def greet(name):
    return f"{name}님, 반가워요"


print(greet("수강생"))

# 4. pathlib과 try/except: 없는 파일을 읽으면 에러가 난다
try:
    Path("없는파일.txt").read_text(encoding="utf-8")
except FileNotFoundError as e:
    print(f"에러: {e}")
