"""
drivers/browser.py — Thin Selenium wrapper used by core.actions.TikTokActions.

Provides a persistent-profile Chrome session (so a login survives across
runs) plus small helper methods (find_element/find_elements with explicit
waits, screenshot-on-failure) that core/actions.py relies on.
"""

import logging
from pathlib import Path
from typing import List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)

from config import Config

logger = logging.getLogger(__name__)


class Browser:
    """
    Owns the actual Selenium WebDriver instance and exposes a small,
    explicit-wait-based API. TikTokActions never touches Selenium directly —
    everything goes through this class, so element-finding behaviour (waits,
    screenshots on failure) stays consistent across every action.
    """

    def __init__(self, config: Config = Config, headless: Optional[bool] = None):
        self.config = config
        self.driver: Optional[WebDriver] = None
        self._launch(headless if headless is not None else config.HEADLESS)

    # ── Lifecycle ────────────────────────────────────────────────────────

    def _launch(self, headless: bool) -> None:
        options = ChromeOptions()

        profile_dir = Path(self.config.USER_DATA_DIR)
        profile_dir.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir}")

        if self.config.BROWSER_BINARY:
            options.binary_location = self.config.BROWSER_BINARY

        if headless:
            options.add_argument("--headless=new")

        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )

        try:
            # Selenium >= 4.6 auto-resolves the matching chromedriver via
            # Selenium Manager — no separate driver download/setup needed.
            self.driver = webdriver.Chrome(options=options)
        except WebDriverException as e:
            logger.error(f"Failed to launch Chrome: {e}")
            raise

        # Best-effort stealth tweak — hides the `navigator.webdriver` flag
        # that some sites use for bot detection. Not bulletproof, just
        # reduces the most trivial detection signal.
        try:
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
            )
        except WebDriverException:
            pass

        self.driver.implicitly_wait(0)  # we use explicit WebDriverWait everywhere instead
        logger.info(f"Browser launched (headless={headless}, profile={profile_dir}).")

    def quit(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
            except WebDriverException as e:
                logger.warning(f"Error while quitting browser: {e}")
            finally:
                self.driver = None
                logger.info("Browser closed.")

    # ── Navigation ───────────────────────────────────────────────────────

    def go_to_page(self, url: str, wait_for_load: bool = True) -> bool:
        try:
            self.driver.get(url)
            if wait_for_load:
                WebDriverWait(self.driver, self.config.DEFAULT_ELEMENT_WAIT_TIMEOUT).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            return True
        except TimeoutException:
            logger.warning(f"Page load timed out for: {url}")
            return True  # page likely still usable even if readyState never settled
        except WebDriverException as e:
            logger.error(f"Navigation to {url} failed: {e}")
            return False

    # ── Element finding (explicit waits) ────────────────────────────────

    def find_element(self, by: str, value: str, timeout: Optional[float] = None) -> Optional[WebElement]:
        wait_time = timeout if timeout is not None else self.config.DEFAULT_ELEMENT_WAIT_TIMEOUT
        try:
            return WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((by, value))
            )
        except TimeoutException:
            raise
        except NoSuchElementException:
            raise

    def find_elements(self, by: str, value: str, timeout: Optional[float] = None) -> List[WebElement]:
        wait_time = timeout if timeout is not None else self.config.DEFAULT_ELEMENT_WAIT_TIMEOUT
        try:
            WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((by, value))
            )
        except TimeoutException:
            return []
        return self.driver.find_elements(by, value)

    def find_element_in_element(
        self, parent: WebElement, by: str, value: str, timeout: Optional[float] = None
    ) -> Optional[WebElement]:
        """Searches for a child element within `parent`, with an explicit
        wait (parent's subtree may still be rendering, e.g. a panel that
        just opened)."""
        wait_time = timeout if timeout is not None else self.config.DEFAULT_ELEMENT_WAIT_TIMEOUT
        try:
            return WebDriverWait(self.driver, wait_time).until(
                lambda d: parent.find_element(by, value)
            )
        except TimeoutException:
            raise
        except NoSuchElementException:
            raise

    # ── Diagnostics ──────────────────────────────────────────────────────

    def save_screenshot(self, filename: str) -> Optional[str]:
        if not self.driver:
            return None
        try:
            out_dir = Path(self.config.SCREENSHOT_DIR)
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / filename
            self.driver.save_screenshot(str(path))
            logger.debug(f"Screenshot saved: {path}")
            return str(path)
        except WebDriverException as e:
            logger.warning(f"Could not save screenshot '{filename}': {e}")
            return None
