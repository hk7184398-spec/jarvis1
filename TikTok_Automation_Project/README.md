# TikTok Automation Project

Selenium-based automation for a **personal TikTok account**: log in, browse
the For You page, like/comment/follow, and pull video links/profile stats.
Built for keyboard-triggered CLI use, with conservative per-session rate
limits so it can't accidentally spam an account into a ban.

## ⚠️ Before you use this

- Automating engagement (likes/follows/comments) is against most platforms'
  Terms of Service if used at scale or for inauthentic engagement. This tool
  is meant for **light personal use on your own account** — not for running
  many accounts, mass-following, or engagement-pod style abuse. Use it
  responsibly and keep the rate limits low.
- TikTok actively fights automation (CAPTCHAs, 2FA, device fingerprinting).
  This bot does **not** attempt to bypass any of that — when it hits a
  CAPTCHA or unexpected page, it stops, saves a screenshot, and reports
  failure rather than guessing.

## Setup

```bash
cd TikTok_Automation_Project
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env and fill in TIKTOK_USERNAME / TIKTOK_PASSWORD
```

Chrome/Chromium must be installed. Selenium 4.6+ auto-downloads the matching
chromedriver via Selenium Manager — no manual driver setup needed.

## Usage

```bash
# First run: log in once. Session is saved to a persistent Chrome profile
# (TIKTOK_USER_DATA_DIR), so you shouldn't need to log in every time after.
python main.py login

# Scroll the feed, liking up to 10 videos (capped by TIKTOK_MAX_LIKES)
python main.py browse --likes 10

# Get follower/following/likes counts for a profile
python main.py profile someusername

# Follow a user
python main.py follow someusername

# Collect unique video links from the current feed
python main.py links --count 10

# Any command can run headless:
python main.py browse --likes 5 --headless
```

## Project layout

```
TikTok_Automation_Project/
  main.py              CLI entry point
  config.py             All settings, read from .env
  core/
    actions.py          TikTokActions — atomic actions (login, like, follow, comment, ...)
  drivers/
    browser.py           Selenium Chrome wrapper (persistent profile, explicit waits, screenshots)
  utils/
    logger.py             Console + file logging setup
    helpers.py             wait_randomly() — human-like delay helper
  screenshots/            Auto-created; failure screenshots land here
  .browser_profile/       Auto-created Chrome persistent profile (git-ignored)
```

## Safety limits

Every session-level command is capped by env vars in `.env`
(`TIKTOK_MAX_LIKES`, `TIKTOK_MAX_FOLLOWS`, `TIKTOK_MAX_COMMENTS`), and
`TIKTOK_ACTION_COOLDOWN` adds a pause between actions so behaviour doesn't
look scripted. Lower these further if you're testing.

## Troubleshooting

- **Login doesn't complete automatically** — TikTok often shows a CAPTCHA or
  slider puzzle on login. The browser window stays open (unless
  `--headless`) so you can solve it manually once; the session then
  persists for future runs.
- **`selenium.common.exceptions.WebDriverException: unable to find
  chromedriver`** — make sure Chrome/Chromium itself is installed; Selenium
  Manager downloads the driver automatically but still needs a browser to
  match against.
- Check `screenshots/` and `tiktok_bot.log` after any failure — every action
  in `core/actions.py` saves a screenshot on failure before returning.
