"""0편: 실습 준비가 끝났는지 확인한다.

실행: uv run --env-file ../.env python check_setup.py
API 키는 한 글자도 출력하지 않는다. "설정됨"인지만 알려 준다.
"""

import os
import sys

problems = []


def check(ok, label, fix):
    print(f"  {'OK' if ok else '!!'}  {label}")
    if not ok:
        problems.append(fix)


def key_state(key):
    if not key:
        return "(없음)"
    if "여기에" in key:
        return "(예시 값 그대로)"
    if not key.startswith("sk-or-"):
        return "(OpenRouter 키가 아님)"
    return "설정됨"


print("1. Python")
major, minor = sys.version_info[:2]
check((major, minor) >= (3, 10), f"Python {major}.{minor}", "Python 3.10 이상 설치")

print("2. openai 패키지")
try:
    import openai
except ImportError:
    openai = None
version = openai.__version__ if openai else "없음"
check(openai is not None, f"openai {version}", "상위 폴더에서 uv sync")

print("3. 환경 변수")
base_url = os.environ.get("OPENAI_BASE_URL", "")
key = os.environ.get("OPENAI_API_KEY", "")
model = os.environ.get("MODEL", "")
check(base_url, f"OPENAI_BASE_URL = {base_url or '(없음)'}", ".env에 주소 넣기")
state = key_state(key)
check(state == "설정됨", f"OPENAI_API_KEY = {state}", ".env에 키 넣기")
check(model, f"MODEL = {model or '(없음)'}", ".env에 MODEL 넣기")
if not (base_url or key or model):
    problems.append("--env-file ../.env를 붙여서 실행했는지 확인")

if problems:
    print("\n준비가 덜 됐습니다. 아래를 고친 뒤 다시 실행하세요.")
    for fix in problems:
        print(f"  - {fix}")
    sys.exit(1)

print("4. 실제 호출 한 번")
HINTS = {401: "키가 틀렸습니다", 402: "크레딧이 부족합니다", 404: "MODEL 이름 확인"}
client = openai.OpenAI()
try:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "한 단어로 인사해줘"}],
        # 3편에서 배우는 가격 상한: 출력 100만 토큰당 $1보다 비싼 제공자는 쓰지 않는다
        extra_body={"provider": {"max_price": {"completion": 1}}},
    )
except openai.APIStatusError as e:
    # 에러 본문에는 계정 정보가 섞일 수 있어서 상태 코드와 안내만 보여 준다
    print(f"  !!  API 오류 {e.status_code}: {HINTS.get(e.status_code, '')}")
    sys.exit(1)
except openai.APIConnectionError:
    print("  !!  서버에 연결하지 못했습니다. 인터넷과 주소를 확인하세요")
    sys.exit(1)

usage = response.usage
cost = (usage.model_extra or {}).get("cost")
billed = f"${cost:.6f}" if cost is not None else "알 수 없음"
print(f"  답변    {(response.choices[0].message.content or '').strip()}")
print(f"  모델    {response.model}")
print(f"  제공자  {(response.model_extra or {}).get('provider')}")
print(f"  토큰    입력 {usage.prompt_tokens} · 출력 {usage.completion_tokens}")
print(f"  청구액  {billed} (usage.cost)")
print("\n준비 완료! 1편에서 만나요.")
