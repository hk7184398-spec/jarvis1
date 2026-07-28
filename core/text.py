import json
import re
from typing import Any


def strip_code_fences(text: str) -> str:
    """Remove a leading ```lang fence and a trailing ``` fence from LLM output."""
    clean = (text or "").strip()
    clean = re.sub(r"^```[a-zA-Z]*\r?\n?", "", clean)
    clean = re.sub(r"\r?\n?```\s*$", "", clean)
    return clean.strip()


def parse_json_response(text: str) -> Any:
    """Parse JSON from an LLM response that may be wrapped in markdown fences."""
    clean = re.sub(r"```(?:json)?", "", (text or "").strip())
    clean = clean.strip().rstrip("`").strip()
    return json.loads(clean)


def is_rate_limit_error(error: BaseException | str) -> bool:
    msg = str(error).lower()
    return "429" in msg or "quota" in msg or "resource_exhausted" in msg
