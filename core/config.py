import json

from core.paths import API_CONFIG_PATH, CONFIG_DIR


def load_config() -> dict:
    try:
        return json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    API_CONFIG_PATH.write_text(json.dumps(data, indent=4), encoding="utf-8")


def update_config(**values) -> dict:
    data = load_config()
    data.update(values)
    save_config(data)
    return data


def config_exists() -> bool:
    return API_CONFIG_PATH.exists()


def get_api_key(name: str = "gemini_api_key", required: bool = True) -> str:
    key = str(load_config().get(name, "")).strip()
    if not key and required:
        raise RuntimeError(f"{name} is missing or empty in {API_CONFIG_PATH}")
    return key


def get_gemini_key(required: bool = True) -> str:
    return get_api_key("gemini_api_key", required)


def get_openrouter_key(required: bool = True) -> str:
    return get_api_key("openrouter_api_key", required)


def get_os() -> str:
    """Returns: 'windows' | 'mac' | 'linux'"""
    return str(load_config().get("os_system", "windows")).lower()


def is_windows() -> bool: return get_os() == "windows"
def is_mac()     -> bool: return get_os() == "mac"
def is_linux()   -> bool: return get_os() == "linux"
