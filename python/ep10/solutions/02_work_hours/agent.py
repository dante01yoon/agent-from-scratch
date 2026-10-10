import json
import os
import re
import shutil
from datetime import date, time
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

client = OpenAI()
MODEL = os.environ["MODEL"]
HERE = Path(__file__).parent

MAX_TURNS = 10
TODAY = date(
    2026, 10, 12
)  # 실습 결과가 날마다 달라지지 않게 "오늘"을 고정한다 (월요일)

# 회사 사람 목록. 모델은 find_person으로 이메일을 찾아야 한다
PEOPLE = {
    "김민수": "minsu.kim@quokka.dev",
    "이지영": "jiyoung.lee@quokka.dev",
    "박준호": "junho.park@quokka.dev",
}

SYSTEM = f"""너는 일정 비서다. 오늘은 {TODAY.isoformat()} (월요일)이다.
사람 이름이 나오면 find_person으로 이메일을 찾고, add_event로 일정을 등록한다.
등록이 끝나면 무엇을 등록했는지 한 줄로 보고한다."""


# ---------- 일정 한 건의 규칙: Pydantic 모델 ----------
class Event(BaseModel):
    title: str = Field(min_length=1, max_length=40, description="일정 제목")
    day: date = Field(description="날짜. YYYY-MM-DD 형식. 예: 2026-10-13")
    start: time = Field(description="시작 시각. 24시간 HH:MM 형식. 예: 15:00")
    minutes: int = Field(ge=15, le=240, description="길이(분). 15~240 사이 정수")
    attendees: list[str] = Field(
        min_length=1, description="참석자 이메일 목록. find_person으로 찾은 값"
    )

    @field_validator("day")
    @classmethod
    def not_past(cls, v: date) -> date:
        if v < TODAY:
            raise ValueError(f"과거 날짜입니다. 오늘({TODAY})이나 그 뒤여야 합니다")
        return v

    @field_validator("minutes")
    @classmethod
    def quarter_hour(cls, v: int) -> int:
        if v % 15:
            raise ValueError("15분 단위여야 합니다 (15, 30, 45, 60 …)")
        return v

    @model_validator(mode="after")
    def work_hours(self) -> "Event":
        start = self.start.hour * 60 + self.start.minute
        if start < 9 * 60 or start + self.minutes > 18 * 60:
            raise ValueError("근무 시간(09:00~18:00) 안에서 시작하고 끝나야 합니다")
        return self

    @field_validator("attendees")
    @classmethod
    def known_people(cls, v: list[str]) -> list[str]:
        unknown = [a for a in v if a not in PEOPLE.values()]
        if unknown:
            raise ValueError(
                f"모르는 이메일입니다: {unknown}. find_person으로 찾으세요"
            )
        return v


# ---------- 도구 ----------
def find_person(root: Path, name: str) -> str:
    for full, email in PEOPLE.items():
        if name and (name in full or full.endswith(name)):
            return json.dumps({"name": full, "email": email}, ensure_ascii=False)
    return f"에러: '{name}'라는 사람을 찾을 수 없습니다"


def add_event(root: Path, **args) -> str:
    events = json.loads((root / "calendar.json").read_text(encoding="utf-8"))
    events.append(args)
    (root / "calendar.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    return f"등록 완료: {args.get('title')} ({len(events)}번째 일정)"


TOOLS = {"find_person": find_person, "add_event": add_event}

# 손으로 쓴 스키마 (1~9편 방식). 검증 없이 돌릴 때 쓴다
HAND_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "day": {"type": "string", "description": "날짜"},
        "start": {"type": "string", "description": "시작 시각"},
        "minutes": {"type": "integer", "description": "길이(분)"},
        "attendees": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "day", "start", "minutes", "attendees"],
}


def schemas(schema: str) -> list[dict]:
    event_schema = Event.model_json_schema() if schema == "pydantic" else HAND_SCHEMA
    return [
        {
            "type": "function",
            "function": {
                "name": "find_person",
                "description": "사람 이름(일부도 가능)으로 회사 이메일을 찾는다.",
                "parameters": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "add_event",
                "description": "캘린더에 일정 하나를 등록한다.",
                "parameters": event_schema,
            },
        },
    ]


def explain(err: ValidationError) -> str:
    """Pydantic 오류를 모델이 고치기 쉬운 한국어 목록으로 바꾼다."""
    lines = []
    for e in err.errors():
        field = ".".join(str(x) for x in e["loc"]) or "(전체)"
        msg = re.sub(r"^Value error, ", "", e["msg"])
        lines.append(f"- {field}: {msg} (받은 값: {e.get('input')!r})")
    return (
        "에러: 인자가 규칙에 맞지 않아 등록하지 않았습니다. 고쳐서 다시 부르세요.\n"
        + "\n".join(lines)
    )


def run_tool(root: Path, name: str, args: dict, validate: bool) -> str:
    if name not in TOOLS:
        raise ValueError(f"없는 도구입니다: {name}")
    if name == "add_event" and validate:
        try:
            event = Event.model_validate(args)
        except ValidationError as err:
            return explain(err)
        args = event.model_dump(mode="json")
    return TOOLS[name](root, **args)


def fresh_calendar(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    (dest / "calendar.json").write_text("[]", encoding="utf-8")
    return dest.resolve()


def run_agent(
    task: str, root: Path, validate: bool, schema="hand", quiet=False
) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": task},
    ]
    calls = []
    for turn in range(1, MAX_TURNS + 1):
        response = client.chat.completions.create(
            model=MODEL,
            tools=schemas(schema),
            messages=messages,
            extra_body={"provider": {"max_price": {"completion": 1}}},
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        if not message.tool_calls:
            return {"answer": message.content, "turns": turn, "calls": calls}
        for call in message.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
                result = run_tool(root, name, args, validate)
            except Exception as err:
                args, result = {}, f"에러: {err}"
            calls.append({"turn": turn, "tool": name, "args": args, "result": result})
            if not quiet:
                shown = json.dumps(args, ensure_ascii=False)
                print(f"[{turn}회차] {name}({shown[:90]})")
                print(f"        → {result.splitlines()[0][:90]}")
                for extra in result.splitlines()[1:]:
                    print(f"          {extra[:100]}")
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )
    return {"answer": "중단: 최대 반복 횟수 도달", "turns": MAX_TURNS, "calls": calls}


def check(root: Path) -> list[str]:
    """저장된 일정이 규칙에 맞는지 사후 검사한다 (검증 없이 저장된 것도 잡아낸다)."""
    problems = []
    for i, raw in enumerate(json.loads((root / "calendar.json").read_text("utf-8"))):
        try:
            Event.model_validate(raw)
        except ValidationError as err:
            fields = sorted({str(e["loc"][0]) for e in err.errors() if e["loc"]})
            problems.append(f"{i + 1}번째 일정: {', '.join(fields)} 잘못됨")
    return problems


CASES = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))


def run_cases(validate: bool, schema: str, title: str) -> None:
    """cases.json의 요청 다섯 개를 한 캘린더에 차례로 요청하고, 결과를 calendar.html로 남긴다."""
    from view import save_calendar

    root = fresh_calendar(HERE / "work")
    for case in CASES:
        print(f"\n요청: {case['task']}")
        result = run_agent(case["task"], root, validate, schema)
        lines = [x for x in (result["answer"] or "").splitlines() if x.strip()]
        print("답:", lines[0][:110] if lines else "(없음)")
    problems = check(root)
    print("\n저장된 일정 규칙 검사:", "문제 없음" if not problems else "")
    for p in problems:
        print("  -", p)
    save_calendar(root, HERE / "calendar.html", title)
    print("캘린더: calendar.html 을 브라우저로 여세요")
