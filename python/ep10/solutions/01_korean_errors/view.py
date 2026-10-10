"""캘린더 화면(HTML) 만들기. 저장된 일정을 주간 표로 그리고, 규칙에 어긋난 일정은 빨갛게 표시한다."""

import html
import json
from datetime import timedelta
from pathlib import Path

from agent import TODAY, Event
from pydantic import ValidationError

STYLE = """
body{background:#14161c;color:#e8e6df;font:17px/1.5 "Noto Sans KR",sans-serif;margin:0;padding:40px 56px}
h1{font-size:30px;margin:0 0 4px} h2{font-size:21px;color:#f2b84b;margin:28px 0 10px}
p.sub{color:#9a988f;margin:0}
.week{display:grid;grid-template-columns:repeat(7,1fr);gap:8px}
.day{background:#1e212a;border-radius:10px;min-height:150px;padding:10px}
.day b{display:block;color:#a9a59a;font-size:15px;margin-bottom:6px}
.ev{background:#26354a;border-left:4px solid #9cc4ff;border-radius:6px;padding:6px 8px;margin:6px 0;font-size:15px}
.ev.bad{background:#3a2226;border-left-color:#e86a6a}
.ev small{display:block;color:#a9a59a}
.bad small.why{color:#ffb3a3}
.out{margin-top:10px;font-size:15px;color:#ffb3a3}
"""
DAYS = "월화수목금토일"
FIELDS = {
    "title": "제목",
    "day": "날짜",
    "start": "시작",
    "minutes": "길이",
    "attendees": "참석자",
}


def problems_of(raw: dict) -> list[str]:
    try:
        Event.model_validate(raw)
    except ValidationError as err:
        return [
            FIELDS.get(str(e["loc"][0]), str(e["loc"][0]))
            for e in err.errors()
            if e["loc"]
        ]
    return []


def card(raw: dict) -> str:
    bad = problems_of(raw)
    who = ", ".join(a.split("@")[0] for a in raw.get("attendees", []))
    why = f'<small class="why">규칙 위반: {", ".join(bad)}</small>' if bad else ""
    return (
        f'<div class="ev{" bad" if bad else ""}">{html.escape(str(raw.get("title")))}'
        f"<small>{html.escape(str(raw.get('start')))[:5]} · {raw.get('minutes')}분 · {html.escape(who)}</small>{why}</div>"
    )


def week_html(events: list[dict]) -> str:
    monday = TODAY - timedelta(days=TODAY.weekday())
    cols = []
    for i in range(14):
        d = monday + timedelta(days=i)
        cards = "".join(card(e) for e in events if str(e.get("day")) == d.isoformat())
        cols.append(
            f'<div class="day"><b>{d.month}/{d.day} ({DAYS[i % 7]})</b>{cards}</div>'
        )
    days = {(monday + timedelta(days=i)).isoformat() for i in range(14)}
    outside = [e for e in events if str(e.get("day")) not in days]
    extra = "".join(
        f'<div class="out">표 밖의 날짜 {html.escape(str(e.get("day")))}: {card(e)}</div>'
        for e in outside
    )
    return f'<div class="week">{"".join(cols)}</div>{extra}'


def page(title: str, sections: list[tuple[str, list[dict]]], sub: str = "") -> str:
    body = "".join(f"<h2>{html.escape(h)}</h2>{week_html(ev)}" for h, ev in sections)
    return (
        f'<!doctype html><meta charset="utf-8"><title>{html.escape(title)}</title>'
        f"<style>{STYLE}</style><h1>{html.escape(title)}</h1><p class='sub'>{html.escape(sub)}</p>{body}"
    )


def save_calendar(root: Path, out: Path, title: str) -> None:
    events = json.loads((root / "calendar.json").read_text(encoding="utf-8"))
    out.write_text(
        page(title, [("이번 주 · 다음 주", events)], f"오늘은 {TODAY}"), "utf-8"
    )
