"""
config.py — Central configuration for the TikTok Automation Project.

Reads everything from environment variables (via a .env file if present) so
credentials never get hardcoded/committed. Copy .env.example to .env and
fill in your own values before running anything.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv is a soft dependency — if it's not installed, the user
    # can still export env vars manually before running the bot.
    pass

BASE_DIR = Path(__file__).resolve().parent


class Config:
    # ── Credentials ──────────────────────────────────────────────────────
    TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME", "")
    TIKTOK_PASSWORD = os.getenv("TIKTOK_PASSWORD", "")

    # ── URLs ─────────────────────────────────────────────────────────────
    LOGIN_URL        = os.getenv("TIKTOK_LOGIN_URL", "https://www.tiktok.com/login/phone-or-email/email")
    FOR_YOU_PAGE_URL = os.getenv("TIKTOK_FYP_URL", "https://www.tiktok.com/foryou")
    PROFILE_BASE_URL = os.getenv("TIKTOK_PROFILE_BASE_URL", "https://www.tiktok.com/@")

    # ── Browser behaviour ────────────────────────────────────────────────
    HEADLESS       = os.getenv("TIKTOK_HEADLESS", "false").strip().lower() == "true"
    BROWSER_BINARY = os.getenv("TIKTOK_BROWSER_BINARY", "")  # optional: path to a specific Chrome/Chromium binary
    USER_DATA_DIR  = os.getenv("TIKTOK_USER_DATA_DIR", str(BASE_DIR / ".browser_profile"))
    SCREENSHOT_DIR = os.getenv("TIKTOK_SCREENSHOT_DIR", str(BASE_DIR / "screenshots"))

    # ── Timing / human-like delays ───────────────────────────────────────
    DEFAULT_ELEMENT_WAIT_TIMEOUT = int(os.getenv("TIKTOK_ELEMENT_WAIT_TIMEOUT", "10"))   # seconds, Selenium waits
    DEFAULT_MIN_DELAY            = float(os.getenv("TIKTOK_MIN_DELAY", "1.0"))            # seconds, general human delay
    DEFAULT_MAX_DELAY            = float(os.getenv("TIKTOK_MAX_DELAY", "3.0"))
    DEFAULT_SCROLL_PAUSE_TIME    = float(os.getenv("TIKTOK_SCROLL_PAUSE", "2.0"))

    # ── Safety / anti-spam rate limits (used by main.py's session runner) ─
    MAX_LIKES_PER_SESSION    = int(os.getenv("TIKTOK_MAX_LIKES", "30"))
    MAX_FOLLOWS_PER_SESSION  = int(os.getenv("TIKTOK_MAX_FOLLOWS", "10"))
    MAX_COMMENTS_PER_SESSION = int(os.getenv("TIKTOK_MAX_COMMENTS", "5"))
    ACTION_COOLDOWN_SECONDS  = float(os.getenv("TIKTOK_ACTION_COOLDOWN", "4.0"))

    @classmethod
    def validate_for_login(cls) -> None:
        """Raises a clear error early if credentials are missing, instead of
        failing deep inside a Selenium call with a confusing stack trace."""
        missing = [
            name for name, val in (
                ("TIKTOK_USERNAME", cls.TIKTOK_USERNAME),
                ("TIKTOK_PASSWORD", cls.TIKTOK_PASSWORD),
            ) if not val
        ]
        if missing:
            raise RuntimeError(
                f"Missing required config values: {', '.join(missing)}. "
                f"Set them in a .env file (see .env.example) or as environment variables."
            )
