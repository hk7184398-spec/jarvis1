import json

from core.files import atomic_write_text, quarantine_corrupt_file, restrict_permissions
from core.paths import API_CONFIG_PATH, CONFIG_DIR


def read_config() -> dict:
    """Strict read — raises RuntimeError describing why the config is unusable."""
    try:
        data = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise RuntimeError(f"api_keys.json not found at: {API_CONFIG_PATH}") from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise RuntimeError(f"{API_CONFIG_PATH} is not valid JSON: {e}") from e
    except OSError as e:
        raise RuntimeError(f"Could not read {API_CONFIG_PATH}: {e}") from e

    if not isinstance(data, dict):
        raise RuntimeError(f"{API_CONFIG_PATH} does not contain a JSON object")
    return data


def load_config() -> dict:
    """Tolerant read — returns {} (and reports the reason) when unreadable."""
    if not API_CONFIG_PATH.exists():
        return {}
    try:
        return read_config()
    except RuntimeError as e:
        print(f"[Config] ❌ {e}")
        return {}


def save_config(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_text(API_CONFIG_PATH, json.dumps(data, indent=4))
    restrict_permissions(API_CONFIG_PATH)


def update_config(**values) -> dict:
    data = {}
    if API_CONFIG_PATH.exists():
        try:
            data = read_config()
        except RuntimeError as e:
            # Keep a copy: rewriting the file would drop every other key
            # (openrouter_api_key, os_system, camera_index, ...) unnoticed.
            print(f"[Config] ⚠️ {e}")
            quarantine_corrupt_file(API_CONFIG_PATH, "Config")

    data.update(values)
    save_config(data)
    return data


def config_exists() -> bool:
    return API_CONFIG_PATH.exists()


def get_api_key(name: str = "gemini_api_key", required: bool = True) -> str:
    key = str(read_config().get(name, "")).strip()
    if not key and required:
        raise RuntimeError(f"'{name}' is missing or empty in {API_CONFIG_PATH}")
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
