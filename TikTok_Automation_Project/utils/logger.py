"""
utils/logger.py — Idempotent logging setup.

`setup_logging()` can safely be called from multiple modules (each module
that uses logging calls it at import time) without duplicating handlers —
guarded by the `_logging_configured` module-level flag, same pattern the
rest of Jarvis's actions modules use.
"""

import logging
import sys
from pathlib import Path

_logging_configured = False


def setup_logging(level: int = logging.INFO, log_file: str = "tiktok_bot.log") -> None:
    global _logging_configured
    if _logging_configured:
        return

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    root.addHandler(console_handler)

    try:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError as e:
        # Non-fatal — console logging still works even if the log file
        # can't be created (e.g. read-only filesystem).
        print(f"[logger] Could not create log file '{log_file}': {e}")

    # Selenium/urllib3 are extremely chatty at INFO — keep them at WARNING
    # so the bot's own log lines aren't drowned out.
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _logging_configured = True
