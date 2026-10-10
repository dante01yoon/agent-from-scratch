"""API 없이 오류 메시지만 확인한다."""

from agent import Event, explain
from pydantic import ValidationError

bad = {
    "title": "",
    "day": "10월 20일",
    "start": "오후 3시",
    "minutes": 300,
    "attendees": [],
}
try:
    Event.model_validate(bad)
except ValidationError as err:
    print(explain(err))
