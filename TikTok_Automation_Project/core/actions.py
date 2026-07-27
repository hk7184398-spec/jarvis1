import logging
from typing import Optional, List, Dict, Any

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
    StaleElementReferenceException,
)

# Project specific imports
from config import Config
from utils.logger import setup_logging
from utils.helpers import wait_randomly
from drivers.browser import Browser

# Initialize logging for this module.
# `setup_logging` is idempotent due to `_logging_configured` check in utils/logger.py.
setup_logging()
logger = logging.getLogger(__name__)


class TikTokActions:
    """
    Implements atomic, specific TikTok actions such as logging in, navigating to profiles,
    liking videos, following users, or commenting, utilizing the browser driver.
    """

    def __init__(self, browser: Browser, config: Config):
        """
        Initializes the TikTokActions with a browser instance and configuration.

        Args:
            browser (Browser): An initialized instance of the Browser driver.
            config (Config): The project configuration object.
        """
        self.browser = browser
        self.driver: WebDriver = browser.driver  # Browser.driver is Optional, but expected to be initialized.
        if not self.driver:
            raise ValueError("Browser driver must be initialized before creating TikTokActions.")
        self.config = config

    def _human_delay(self, min_s: Optional[float] = None, max_s: Optional[float] = None) -> None:
        """
        Pauses execution for a random duration, mimicking human behavior.

        Args:
            min_s (Optional[float]): Minimum seconds to wait. Defaults to Config.DEFAULT_MIN_DELAY.
            max_s (Optional[float]): Maximum seconds to wait. Defaults to Config.DEFAULT_MAX_DELAY.
        """
        min_seconds = min_s if min_s is not None else self.config.DEFAULT_MIN_DELAY
        max_seconds = max_s if max_s is not None else self.config.DEFAULT_MAX_DELAY
        wait_randomly(min_seconds, max_seconds)

    def navigate_to_url(self, url: str, wait_for_load: bool = True) -> bool:
        """
        Navigates the browser to the specified URL.

        Args:
            url (str): The URL to navigate to.
            wait_for_load (bool): Whether to wait for the page to fully load.

        Returns:
            bool: True if navigation was successful, False otherwise.
        """
        logger.info(f"Navigating to URL: {url}")
        return self.browser.go_to_page(url, wait_for_load=wait_for_load)

    def go_to_for_you_page(self) -> bool:
        """
        Navigates to the TikTok 'For You' page.

        Returns:
            bool: True if navigation was successful, False otherwise.
        """
        logger.info("Navigating to For You page.")
        return self.navigate_to_url(self.config.FOR_YOU_PAGE_URL)

    def go_to_profile_page(self, username: str) -> bool:
        """
        Navigates to a specific user's TikTok profile page.

        Args:
            username (str): The username of the profile to visit (without the '@').

        Returns:
            bool: True if navigation was successful, False otherwise.
        """
        profile_url = f"{self.config.PROFILE_BASE_URL}{username}"
        logger.info(f"Navigating to profile page: {profile_url}")
        return self.navigate_to_url(profile_url)

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Attempts to log into TikTok using provided or configured credentials.

        Args:
            username (Optional[str]): TikTok username. If None, uses Config.TIKTOK_USERNAME.
            password (Optional[str]): TikTok password. If None, uses Config.TIKTOK_PASSWORD.

        Returns:
            bool: True if login appears successful, False otherwise.
        """
        actual_username = username or self.config.TIKTOK_USERNAME
        actual_password = password or self.config.TIKTOK_PASSWORD

        if not actual_username or not actual_password:
            logger.error("TikTok username or password not provided in config or parameters for login.")
            return False

        logger.info(f"Attempting to log in as {actual_username}...")
        self.navigate_to_url(self.config.LOGIN_URL)
        self._human_delay()  # Wait for login page to load

        try:
            # TikTok often has multiple login options. Try to click "Use phone / email / username" tab.
            try:
                email_username_tab = self.browser.find_element(
                    By.XPATH, "//p[contains(text(), 'Use phone / email / username')] | //span[contains(text(), 'Email / Username')]",
                    timeout=5
                )
                if email_username_tab:
                    email_username_tab.click()
                    self._human_delay(1, 2)
            except (NoSuchElementException, TimeoutException):
                logger.debug("Email/username tab not found or not needed, proceeding directly to inputs.")

            # Find username/email input, password input, and login button
            username_input = self.browser.find_element(By.NAME, "username", timeout=self.config.DEFAULT_ELEMENT_WAIT_TIMEOUT)
            password_input = self.browser.find_element(By.XPATH, "//input[@type='password' or @name='password']", timeout=self.config.DEFAULT_ELEMENT_WAIT_TIMEOUT)
            login_button = self.browser.find_element(By.XPATH, "//button[@type='submit' and contains(., 'Log in')] | //button[@data-e2e='login-button']", timeout=self.config.DEFAULT_ELEMENT_WAIT_TIMEOUT)

            if not username_input or not password_input or not login_button:
                logger.error("Could not find all login elements (username/password inputs or login button).")
                self.browser.save_screenshot("login_elements_not_found.png")
                return False

            username_input.send_keys(actual_username)
            self._human_delay(0.5, 1.5)
            password_input.send_keys(actual_password)
            self._human_delay(0.5, 1.5)
            login_button.click()
            # Allow longer wait for post-login redirection and page load
            self._human_delay(self.config.DEFAULT_ELEMENT_WAIT_TIMEOUT, self.config.DEFAULT_ELEMENT_WAIT_TIMEOUT + 5)

            # Check if login was successful (e.g., by checking URL or presence of a known element like FYP)
            current_url = self.driver.current_url
            if self.config.FOR_YOU_PAGE_URL in current_url or "feed" in current_url or "recommend" in current_url:
                logger.info("Successfully logged in.")
                return True
            else:
                logger.warning(f"Login attempt finished, but current URL is {current_url}. Might have failed or encountered CAPTCHA/2FA.")
                self.browser.save_screenshot("login_post_attempt_url_mismatch.png")
                # Further checks could be added here, e.g., looking for error messages or CAPTCHA elements
                return False

        except (NoSuchElementException, TimeoutException) as e:
            logger.error(f"Failed to find login elements or timeout reached: {e}")
            self.browser.save_screenshot("login_failure.png")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during login: {e}")
            self.browser.save_screenshot("login_unexpected_error.png")
            return False

    def _find_video_actions_panel(self) -> Optional[WebElement]:
        """
        Tries to find the common sidebar element containing like, comment, share buttons.

        Returns:
            Optional[WebElement]: The video action panel element if found, None otherwise.
        """
        # Selectors are highly dynamic and need to be found robustly.
        selectors = [
            (By.CSS_SELECTOR, "div[data-e2e='video-action-panel']"),
            (By.XPATH, "//div[contains(@class, 'DivVideoActionWrapper')]"),
            (By.XPATH, "//div[contains(@id, 'tiktok-live-feed-app')]//div[contains(@class, 'DivVideoActionWrapper')]")
        ]
        for by, value in selectors:
            try:
                panel = self.browser.find_element(by, value, timeout=self.config.DEFAULT_ELEMENT_WAIT_TIMEOUT // 2)
                if panel and panel.is_displayed():
                    return panel
            except (NoSuchElementException, TimeoutException):
                continue
        logger.warning("Could not find the video action panel.")
        return None

    def _interact_with_button_in_panel(self, button_type: str) -> bool:
        """
        Helper to find and click a button (like, comment) within the video action panel.

        Args:
            button_type (str): The type of button to interact with (e.g., 'like', 'comment').

        Returns:
            bool: True if the action was performed (or already in that state), False otherwise.
        """
        panel = self._find_video_actions_panel()
        if not panel:
            logger.error(f"Cannot perform {button_type} action: video action panel not found.")
            return False

        try:
            button_element: Optional[WebElement] = None
            if button_type == "like":
                # Find the like button and check if it's already liked
                like_button_container = self.browser.find_element_in_element(panel, By.CSS_SELECTOR, "button[data-e2e='like-button']", timeout=2)
                if like_button_container:
                    # Check for presence of a "filled" heart icon (indicates liked state)
                    # This check is fragile and depends on specific SVG structure/attributes
                    # A more robust check might involve 'aria-pressed' attribute if available
                    liked_svg = self.browser.find_element_in_element(like_button_container, By.XPATH, ".//*[name()='svg'][@data-icon-type='heart-fill']", timeout=1)
                    if liked_svg:
                        logger.info("Video is already liked.")
                        return True
                    else:
                        button_element = like_button_container
            elif button_type == "comment":
                button_element = self.browser.find_element_in_element(panel, By.CSS_SELECTOR, "button[data-e2e='comment-button']", timeout=2)
            elif button_type == "share":
                button_element = self.browser.find_element_in_element(panel, By.CSS_SELECTOR, "button[data-e2e='share-button']", timeout=2)

            if button_element and button_element.is_displayed() and button_element.is_enabled():
                logger.info(f"Clicking {button_type} button.")
                button_element.click()
                self._human_delay()
                logger.info(f"Successfully performed {button_type} action.")
                return True
            else:
                logger.warning(f"{button_type} button not found, not displayed, or not enabled.")
                return False

        except (NoSuchElementException, TimeoutException):
            logger.warning(f"{button_type} button not found within video action panel or timed out.")
            return False
        except Exception as e:
            logger.error(f"Error while trying to click {button_type} button: {e}")
            self.browser.save_screenshot(f"{button_type}_click_error.png")
            return False

    def like_current_video(self) -> bool:
        """
        Attempts to like the currently viewed video.

        Returns:
            bool: True if the video was liked (or already liked), False otherwise.
        """
        logger.info("Attempting to like the current video.")
        return self._interact_with_button_in_panel("like")

    def comment_on_current_video(self, comment_text: str) -> bool:
        """
        Adds a comment to the currently viewed video.

        Args:
            comment_text (str): The text of the comment to post.

        Returns:
            bool: True if the comment was successfully posted, False otherwise.
        """
        logger.info(f"Attempting to comment '{comment_text}' on the current video.")
        if not comment_text:
            logger.warning("Comment text is empty, skipping comment.")
            return False

        # First, click the comment button to open the comment section
        if not self._interact_with_button_in_panel("comment"):
            logger.error("Failed to click comment button to open comment section.")
            return False

        self._human_delay(2, 4)  # Wait for comment section to load/open

        try:
            # Find the comment input field
            # TikTok's comment input is often a contenteditable div
            comment_input = self.browser.find_element(
                By.XPATH, "//div[@data-e2e='comment-input']//div[@contenteditable='true'] | //div[contains(@class, 'DivCommentInputContainer')]//div[@contenteditable='true']",
                timeout=self.config.DEFAULT_ELEMENT_WAIT_TIMEOUT
            )
            if not comment_input:
                logger.error("Could not find comment input field.")
                self.browser.save_screenshot("comment_input_not_found.png")
                return False

            comment_input.send_keys(comment_text)
            self._human_delay(1, 2)

            # Find and click the post button
            post_button = self.browser.find_element(
                By.XPATH, "//button[@data-e2e='comment-post-button'] | //button[contains(@class, 'ButtonPost')] | //button[text()='Post']",
                timeout=self.config.DEFAULT_ELEMENT_WAIT_TIMEOUT
            )
            if not post_button or not post_button.is_enabled():
                logger.error("Could not find or interact with comment post button (might be disabled).")
                self.browser.save_screenshot("comment_post_button_issue.png")
                return False

            post_button.click()
            self._human_delay(2, 4)  # Wait for comment to post
            logger.info(f"Successfully posted comment: '{comment_text}'.")
            return True

        except (NoSuchElementException, TimeoutException) as e:
            logger.error(f"Failed to find comment elements (input or post button): {e}")
            self.browser.save_screenshot("comment_failure.png")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred while commenting: {e}")
            self.browser.save_screenshot("comment_unexpected_error.png")
            return False

    def follow_user(self, username: Optional[str] = None) -> bool:
        """
        Follows the user currently displayed on their profile page or in a video context.
        If a username is provided, it first navigates to the user's profile.

        Args:
            username (Optional[str]): The username of the user to follow. If None,
                                      attempts to follow the user on the current page.

        Returns:
            bool: True if the user was followed (or already following), False otherwise.
        """
        if username:
            if not self.go_to_profile_page(username):
                logger.error(f"Failed to navigate to {username}'s profile to follow.")
                return False
            self._human_delay(2, 4)  # Wait for profile page to load

        logger.info(f"Attempting to follow user: {username or 'current profile'}")

        try:
            # Look for a common 'Follow' button. This varies greatly.
            # Check for "Following" button first to see if already followed
            try:
                following_button = self.browser.find_element(
                    By.XPATH, "//button[contains(., 'Following')] | //button[@data-e2e='follow-button'][contains(@class, 'active')]",
                    timeout=3
                )
                if following_button and following_button.is_displayed():
                    logger.info("User is already followed.")
                    return True
            except (NoSuchElementException, TimeoutException):
                pass # Not already following, proceed to find 'Follow' button

            follow_button = self.browser.find_element(
                By.XPATH, "//button[contains(., 'Follow') and not(contains(., 'Following')) and not(contains(., 'Unfollow'))] | //button[@data-e2e='follow-button']",
                timeout=self.config.DEFAULT_ELEMENT_WAIT_TIMEOUT
            )

            if follow_button and follow_button.is_displayed() and follow_button.is_enabled():
                logger.info("Clicking follow button.")
                follow_button.click()
                self._human_delay(2, 4)  # Wait for action to register
                logger.info(f"Successfully followed user: {username or 'current profile'}.")
                return True
            else:
                logger.warning("Follow button not found, not displayed, not enabled, or user might already be followed.")
                self.browser.save_screenshot("follow_button_issue.png")
                return False

        except (NoSuchElementException, TimeoutException) as e:
            logger.error(f"Failed to find follow button or timeout reached: {e}")
            self.browser.save_screenshot("follow_failure.png")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred while trying to follow: {e}")
            self.browser.save_screenshot("follow_unexpected_error.png")
            return False

    def scroll_feed(self, scroll_count: int = 1) -> None:
        """
        Scrolls down the current page/feed multiple times.

        Args:
            scroll_count (int): The number of times to scroll down.
        """
        if scroll_count <= 0:
            logger.info("Scroll count is 0 or less, no scrolling performed.")
            return

        logger.info(f"Scrolling feed {scroll_count} time(s).")
        for i in range(scroll_count):
            logger.debug(f"Performing scroll {i + 1}/{scroll_count}")
            # This simulates a 'Page Down' or scrolling to the bottom of the viewport
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self._human_delay(self.config.DEFAULT_SCROLL_PAUSE_TIME, self.config.DEFAULT_SCROLL_PAUSE_TIME + 1.0)  # Pause after each scroll
        logger.info("Finished scrolling feed.")

    def get_video_links_from_feed(self, count: int = 5, max_scrolls: int = 3) -> List[str]:
        """
        Attempts to extract unique video links from the current feed view.
        May scroll to find more videos if needed, up to `max_scrolls` times.

        Args:
            count (int): The desired number of unique video links to collect.
            max_scrolls (int): The maximum number of times to scroll down to find more videos.

        Returns:
            List[str]: A list of unique video URLs.
        """
        logger.info(f"Attempting to get {count} unique video links from the feed (max scrolls: {max_scrolls}).")
        unique_links = set()
        scrolls_performed = 0

        while len(unique_links) < count and scrolls_performed <= max_scrolls:
            self._human_delay(1, 2)  # Give some time for content to load after scroll/initial page load
            try:
                # Find elements that contain video links. This selector will vary.
                # Common TikTok video link structure usually involves an <a> tag
                # wrapping the video preview or a specific data attribute.
                video_elements = self.browser.find_elements(By.XPATH, "//div[@data-e2e='feed-video-card']//a[@href] | //a[contains(@href, '/video/')][div[contains(@class, 'tiktok-web-app-content')]]")

                if not video_elements:
                    logger.warning("No video elements found with current selectors. Performing scroll to find more.")
                    self.scroll_feed(1)
                    scrolls_performed += 1
                    continue

                for element in video_elements:
                    href = element.get_attribute("href")
                    if href and "/video/" in href:
                        clean_href = href.split("?")[0]  # Remove query parameters
                        if clean_href not in unique_links:
                            unique_links.add(clean_href)
                            if len(unique_links) >= count:
                                break
            except StaleElementReferenceException:
                logger.warning("Stale element reference encountered while getting video links, re-attempting.")
                self.scroll_feed(1) # Scroll to refresh context
                scrolls_performed += 1
            except (NoSuchElementException, TimeoutException):
                logger.warning("No video links found on the page after initial attempts. Retrying with scroll.")
                self.scroll_feed(1)
                scrolls_performed += 1
            except Exception as e:
                logger.error(f"An unexpected error occurred while getting video links: {e}")
                self.browser.save_screenshot("get_video_links_error.png")
                scrolls_performed += 1

            if len(unique_links) < count and scrolls_performed < max_scrolls:
                self.scroll_feed(1)  # Scroll to find more videos if needed
                scrolls_performed += 1
            else:
                break  # Exit if enough links found or max scrolls reached

        logger.info(f"Found {len(unique_links)} unique video links.")
        return list(unique_links)

    def extract_profile_counts(self, username: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Navigates to a user's profile (or uses current page) and extracts follower/following/likes counts.

        Args:
            username (Optional[str]): The username of the profile to extract counts from.
                                      If None, extracts from the currently loaded profile page.

        Returns:
            Optional[Dict[str, str]]: A dictionary with 'followers', 'following', 'likes' counts as strings,
                                      or None if counts could not be extracted.
        """
        if username:
            if not self.go_to_profile_page(username):
                logger.error(f"Failed to navigate to {username}'s profile to extract counts.")
                return None
            self._human_delay(2, 4)  # Wait for profile page to load

        logger.info(f"Attempting to extract profile counts for {username or 'current profile'}.")

        try:
            counts = {}
            # Selectors for follower/following/likes counts are typically strong tags with data-e2e attributes
            follower_count_element = self.browser.find_element(By.CSS_SELECTOR, "strong[data-e2e='followers-count']", timeout=5)
            following_count_element = self.browser.find_element(By.CSS_SELECTOR, "strong[data-e2e='following-count']", timeout=5)
            likes_count_element = self.browser.find_element(By.CSS_SELECTOR, "strong[data-e2e='likes-count']", timeout=5)

            if follower_count_element and follower_count_element.is_displayed():
                counts['followers'] = follower_count_element.text
            if following_count_element and following_count_element.is_displayed():
                counts['following'] = following_count_element.text
            if likes_count_element and likes_count_element.is_displayed():
                counts['likes'] = likes_count_element.text

            if counts:
                logger.info(f"Extracted counts: {counts}")
                return counts
            else:
                logger.warning("No follower/following/likes counts found on the page.")
                self.browser.save_screenshot("profile_counts_not_found.png")
                return None

        except (NoSuchElementException, TimeoutException) as e:
            logger.error(f"Failed to find profile count elements: {e}")
            self.browser.save_screenshot("profile_counts_failure.png")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while extracting profile counts: {e}")
            self.browser.save_screenshot("profile_counts_unexpected_error.png")
            return None
