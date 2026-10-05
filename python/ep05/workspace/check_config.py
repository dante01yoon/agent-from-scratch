import json

with open("config/server.json", encoding="utf-8") as f:
    config = json.load(f)

problems = []
if not 1 <= config["port"] <= 65535:
    problems.append("port는 1~65535 사이여야 합니다")
if not 1000 <= config["timeoutMs"] <= 30000:
    problems.append("timeoutMs는 1000~30000 사이여야 합니다")

print("\n".join(problems) if problems else "설정 검사 통과")
