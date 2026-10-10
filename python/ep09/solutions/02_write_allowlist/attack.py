import sys

from agent import attack_once

# 사용: uv run --env-file ../../../.env python attack.py [none|prompt|guard]
attack_once(sys.argv[1] if len(sys.argv) > 1 else "none")
