import sys
import time

from agent import HERE, attack_once
from tracer import Tracer

# 사용: uv run --env-file ../.env python 01_record.py [none|prompt|guard]
defense = sys.argv[1] if len(sys.argv) > 1 else "none"
path = HERE / "traces" / f"{time.strftime('%H%M%S')}-{defense}.jsonl"
attack_once(defense, tracer=Tracer(path))
print(f"\n기록: {path.relative_to(HERE)}")
