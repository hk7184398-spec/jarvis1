from core.config import config_exists, load_config, update_config
from core.files import restrict_permissions
from core.paths import API_CONFIG_PATH, BASE_DIR, CONFIG_DIR, get_base_dir

CONFIG_FILE = API_CONFIG_PATH

__all__ = [
    "BASE_DIR", "CONFIG_DIR", "CONFIG_FILE", "config_exists", "ensure_config_dir",
    "get_base_dir", "get_gemini_key", "is_configured", "load_api_keys",
    "restrict_permissions", "save_api_keys",
]


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def save_api_keys(gemini_api_key: str) -> None:
    update_config(gemini_api_key=gemini_api_key.strip())


def load_api_keys() -> dict:
    return load_config()


def get_gemini_key() -> str | None:
    return load_api_keys().get("gemini_api_key")


def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)
