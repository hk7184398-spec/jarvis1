"""
main.py — Entry point for the TikTok Automation Project (engagement bot).

Usage:
    python main.py login                       # log in once, save session in the persistent profile
    python main.py browse --likes 10            # scroll the For You page, liking up to N videos
    python main.py profile <username>            # visit a profile, print follower/following/likes counts
    python main.py follow <username>              # follow a specific user
    python main.py links --count 10               # collect N unique video links from the current feed

Every run is capped by the safety limits in config.py
(TIKTOK_MAX_LIKES/FOLLOWS/COMMENTS per session) so a bad run can't spam an
account into a ban. This project automates a personal account's own
browsing session — it does not attempt to bypass CAPTCHAs, 2FA, or any
anti-bot protections, and stops (with a screenshot) whenever TikTok's UI
doesn't match what's expected rather than guessing.
"""

import argparse
import logging
import sys
import time

from config import Config
from utils.logger import setup_logging
from drivers.browser import Browser
from core.actions import TikTokActions

setup_logging()
logger = logging.getLogger(__name__)


def build_bot(headless: bool = False) -> TikTokActions:
    browser = Browser(Config, headless=headless)
    return TikTokActions(browser, Config)


def cmd_login(args) -> int:
    Config.validate_for_login()
    bot = build_bot(headless=args.headless)
    try:
        ok = bot.login()
        if ok:
            print("✅ Login successful — session saved in the persistent browser profile.")
            return 0
        print("❌ Login did not complete automatically (check the screenshot in the screenshots/ folder — "
              "CAPTCHA/2FA may need a manual step in the open browser window).")
        return 1
    finally:
        bot.browser.quit()


def cmd_browse(args) -> int:
    bot = build_bot(headless=args.headless)
    likes_done = 0
    try:
        if not bot.go_to_for_you_page():
            print("❌ Could not open the For You page.")
            return 1

        max_likes = min(args.likes, Config.MAX_LIKES_PER_SESSION)
        if args.likes > Config.MAX_LIKES_PER_SESSION:
            print(f"⚠️  Requested {args.likes} likes, capped at {Config.MAX_LIKES_PER_SESSION} "
                  f"(TIKTOK_MAX_LIKES) to avoid spam-flagging the account.")

        while likes_done < max_likes:
            if bot.like_current_video():
                likes_done += 1
                print(f"👍 Liked video {likes_done}/{max_likes}")
            time.sleep(Config.ACTION_COOLDOWN_SECONDS)
            bot.scroll_feed(1)

        print(f"✅ Session complete — {likes_done} video(s) liked.")
        return 0
    finally:
        bot.browser.quit()


def cmd_profile(args) -> int:
    bot = build_bot(headless=args.headless)
    try:
        counts = bot.extract_profile_counts(args.username)
        if counts:
            print(f"📊 @{args.username} — followers: {counts.get('followers', '?')}, "
                  f"following: {counts.get('following', '?')}, likes: {counts.get('likes', '?')}")
            return 0
        print(f"❌ Could not extract counts for @{args.username}.")
        return 1
    finally:
        bot.browser.quit()


def cmd_follow(args) -> int:
    bot = build_bot(headless=args.headless)
    try:
        ok = bot.follow_user(args.username)
        print(f"{'✅ Followed' if ok else '❌ Could not follow'} @{args.username}.")
        return 0 if ok else 1
    finally:
        bot.browser.quit()


def cmd_links(args) -> int:
    bot = build_bot(headless=args.headless)
    try:
        if not bot.go_to_for_you_page():
            print("❌ Could not open the For You page.")
            return 1
        links = bot.get_video_links_from_feed(count=args.count, max_scrolls=args.max_scrolls)
        for link in links:
            print(link)
        print(f"✅ Found {len(links)} link(s).", file=sys.stderr)
        return 0
    finally:
        bot.browser.quit()


def main() -> int:
    parser = argparse.ArgumentParser(description="TikTok Automation Project — personal-account engagement bot.")
    parser.add_argument("--headless", action="store_true", help="Run Chrome headless (default: visible window).")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Log in and persist the session.")

    p_browse = sub.add_parser("browse", help="Scroll the For You page, liking videos.")
    p_browse.add_argument("--likes", type=int, default=5, help="How many videos to like this session.")

    p_profile = sub.add_parser("profile", help="Extract follower/following/likes counts for a profile.")
    p_profile.add_argument("username", help="TikTok username, without the @.")

    p_follow = sub.add_parser("follow", help="Follow a user.")
    p_follow.add_argument("username", help="TikTok username, without the @.")

    p_links = sub.add_parser("links", help="Collect unique video links from the current feed.")
    p_links.add_argument("--count", type=int, default=10)
    p_links.add_argument("--max-scrolls", dest="max_scrolls", type=int, default=5)

    args = parser.parse_args()

    handlers = {
        "login": cmd_login,
        "browse": cmd_browse,
        "profile": cmd_profile,
        "follow": cmd_follow,
        "links": cmd_links,
    }

    try:
        return handlers[args.command](args)
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
