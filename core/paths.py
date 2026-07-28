import sys
from pathlib import Path


def get_base_dir() -> Path:
    """Project root, or the executable directory when frozen."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = get_base_dir()
CONFIG_DIR      = BASE_DIR / "config"
API_CONFIG_PATH = CONFIG_DIR / "api_keys.json"
MEMORY_PATH     = BASE_DIR / "memory" / "long_term.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
