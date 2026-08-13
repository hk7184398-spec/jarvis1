"""
utils/helpers.py — Small shared helpers.
"""

import random
import time


def wait_randomly(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """
    Sleeps for a random duration between min_seconds and max_seconds,
    mimicking human reaction/reading time between actions. Used throughout
    core/actions.py instead of fixed sleeps, so the bot's timing pattern
    isn't trivially fingerprinted.
    """
    if max_seconds < min_seconds:
        min_seconds, max_seconds = max_seconds, min_seconds
    time.sleep(random.uniform(max(0.0, min_seconds), max(0.0, max_seconds)))
