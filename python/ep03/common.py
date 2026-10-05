from pathlib import Path

WORKSPACE = (Path(__file__).parent / "workspace").resolve()

# 100만 토큰당 달러 (입력, 출력). 2026-10-04 OpenRouter 기준. 가격은 바뀌니 openrouter.ai/models에서 확인
PRICES = {
    "deepseek/deepseek-v4-pro": (0.21, 0.42),
    "z-ai/glm-5.3-flash": (0.15, 0.50),
}


def cost_usd(model: str, usage) -> float:
    if model not in PRICES:
        raise KeyError(f"PRICES에 {model} 가격을 넣어 주세요 (openrouter.ai/models)")
    price_in, price_out = PRICES[model]
    return (
        usage.prompt_tokens * price_in + usage.completion_tokens * price_out
    ) / 1_000_000


def billed_usd(usage) -> float | None:
    # OpenRouter가 응답에 넣어 주는 실제 청구액. 다른 서버(가짜 서버 등)에는 없다
    return (usage.model_extra or {}).get("cost")


def safe_path(path: str) -> Path:
    full = (WORKSPACE / path).resolve()
    if not full.is_relative_to(WORKSPACE):
        raise PermissionError("workspace 밖의 파일은 읽을 수 없습니다")
    return full


def read_file(path: str) -> str:
    full = safe_path(path)
    if not full.is_file():
        raise FileNotFoundError(f"파일이 없습니다: {path}")
    return full.read_text(encoding="utf-8")


def list_files(path: str = ".") -> str:
    files = [p for p in safe_path(path).rglob("*") if p.is_file()]
    names = sorted(str(p.relative_to(WORKSPACE)) for p in files)
    return "\n".join(names) or "(파일 없음)"


TOOLS = {"read_file": read_file, "list_files": list_files}
# 도구가 실패할 때 나는 예외. 이것만 잡아서 모델에게 돌려준다
TOOL_ERRORS = (OSError, ValueError, TypeError)

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "workspace 폴더 안의 파일 내용을 읽는다. path는 workspace 기준 상대 경로다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "예: README.md"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "workspace 안의 파일 목록을 돌려준다. path를 주면 그 폴더 아래만 본다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "예: config. 생략하면 전체",
                    }
                },
            },
        },
    },
]


def run_tool(name: str, args: dict) -> str:
    if name not in TOOLS:
        raise ValueError(
            f"없는 도구입니다: {name} (쓸 수 있는 도구: {', '.join(TOOLS)})"
        )
    return TOOLS[name](**args)
