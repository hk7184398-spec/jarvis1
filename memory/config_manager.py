import json
import sys
from datetime import datetime
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR    = get_base_dir()
CONFIG_DIR  = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def config_exists() -> bool:
    return CONFIG_FILE.exists()


def save_api_keys(gemini_api_key: str) -> None:
    ensure_config_dir()

    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
            # Keep a copy: rewriting the file would drop every other key
            # (openrouter_api_key, os_system, camera_index, ...) unnoticed.
            backup = CONFIG_FILE.with_suffix(
                f".corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            )
            print(f"⚠️  api_keys.json is unreadable ({e}) — backing up to {backup}")
            try:
                CONFIG_FILE.replace(backup)
            except OSError as backup_err:
                print(f"❌ Could not back up api_keys.json: {backup_err}")
            data = {}

    if not isinstance(data, dict):
        print("⚠️  api_keys.json did not contain a JSON object — starting fresh")
        data = {}

    data["gemini_api_key"] = gemini_api_key.strip()

    CONFIG_FILE.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )


def load_api_keys() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"❌ Failed to load {CONFIG_FILE}: {e}")
        return {}


def get_gemini_key() -> str | None:
    return load_api_keys().get("gemini_api_key")


def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)