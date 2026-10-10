# agent-from-scratch

프레임워크 없이 Python으로 AI 에이전트를 처음부터 만들어 보는 강의 **「에이전트 개발 입문」**의 예제 코드입니다.
1편의 `while` 문 하나에서 시작해 8편에서 작은 코딩 에이전트를 완성합니다. 9편부터는 보너스 "안전과 신뢰성"입니다.

모델은 [OpenRouter](https://openrouter.ai)를 거쳐 DeepSeek·GLM 같은 저렴한 모델을 [OpenAI Python SDK](https://github.com/openai/openai-python)로 부릅니다.

## 준비

- Python 3.10 이상, [uv](https://docs.astral.sh/uv/)
- OpenRouter API 키 ([키 만들기](https://openrouter.ai/settings/keys))

```bash
cd python
uv sync
cp .env.example .env   # .env를 열어 OpenRouter 키를 넣습니다 (깃에 올리지 마세요)
cd ep00 && uv run --env-file ../.env python check_setup.py
```

마지막 줄에 `준비 완료!`가 나오면 됩니다. 점검 스크립트는 키를 출력하지 않습니다.

## 편 구성

| 편 | 주제 | 폴더 |
|---|---|---|
| 0 | 오리엔테이션 — 만들 것·필요한 것·기초 지식, 실습 준비 점검 | `ep00/` |
| 1 | 에이전트는 결국 while 문이다 | `ep01/` |
| 2 | 도구 설계 — 모델이 잘 쓰는 도구, 못 쓰는 도구 | `ep02/` |
| 3 | 실패와 비용 다루기 | `ep03/` |
| 4 | 기억 — 대화 기록과 장기 기억 | `ep04/` |
| 5 | 사람 승인 넣기 | `ep05/` |
| 6 | 평가 — "잘 된다"를 숫자로 재기 | `ep06/` |
| 7 | 웹 화면 입히기 (로컬 서버) | `ep07/` |
| 8 | 종합 — 미니 코딩 에이전트 | `ep08/` |
| 9 | 보너스 · 프롬프트 인젝션 — 직접 공격해 보고 막기 | `ep09/` |
| 10 | 보너스 · 도구 인자 검증 — 모델의 실수를 스스로 고치게 (Pydantic) | `ep10/` |

각 편 폴더로 들어가 `uv run --env-file ../.env python <파일>`로 실행합니다. 편마다 폴더가 독립적이라 어느 편부터 봐도 됩니다.
과제의 완성 코드는 각 편의 `solutions/`에 있습니다. 단계별 글 튜토리얼과 과제 해설은 강의 수업 자료로 제공됩니다.

## 참고

- 9편 `sample_project/deploy.env`의 키는 연습용 가짜 값입니다. 진짜 키를 실습 폴더에 두지 마세요.

- 4편부터는 모든 모델 호출에 OpenRouter 가격 상한(`provider.max_price`)을 넣었습니다. 같은 모델도 제공업체마다 가격이 크게 다를 수 있어서입니다 (3편에서 다룹니다).
- 3편 `fake_server.py`는 API 키 없이 실패 상황(깨진 JSON, 429·500 오류 등)을 재현하는 연습용 가짜 서버입니다.
- 7편 서버는 `127.0.0.1`에서만 열립니다.
- 5편·8편의 명령 실행·파일 쓰기 도구는 교육용 안전장치가 들어 있지만, 실습은 이 저장소 안의 작업 폴더에서만 하세요.
- 코드는 `ruff format`으로 정리했습니다: `uv tool run ruff format --check . && uv tool run ruff check .`

## 라이선스

코드는 MIT 라이선스입니다. 강의 영상과 수업 자료는 포함되지 않습니다.
