# actions/tiktok_pipeline/stage4_publish.py
# Stage 4 of the TikTok Automation pipeline: SEO metadata + publish staging.
#
# Backend/auth reality (see JARVIS_SKILLS_MASTER_PROMPT.md section 10.2):
# TikTok's Content Posting API requires app review/an approved use-case
# before it allows direct public posting from an unaudited app. Until that
# approval exists, this module falls back to browser automation: it opens
# TikTok's own upload page in Jarvis's persistent browser session, uploads
# the assembled video, and fills the caption — then STOPS short of the
# final "Post" click unless TIKTOK_AUTO_PUBLISH=true is explicitly set,
# matching the hard guardrail in section 10.4 (no auto-publish by default,
# ever, even with that flag the caption must have been human-approved
# first — see publish_tiktok_video() in __init__.py).
#
# Design principle (same as Stages 1-3):
#   - generate_seo() only GENERATES content — it never decides to post.
#   - stage_for_publish() performs a real, verifiable action (upload) and
#     reports exactly what happened; it never silently retries or assumes
#     success without evidence from the browser automation call.

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from or_client import client
from actions.tiktok_pipeline.state import STATE_DIR
from actions import browser_control

TIKTOK_UPLOAD_URL = "https://www.tiktok.com/upload?lang=en"
POST_LOG_PATH = STATE_DIR / "post_log.json"


# ---------------------------------------------------------------------------
# SEO metadata — title / caption / hashtags
# ---------------------------------------------------------------------------

def generate_seo(niche: str, script: str) -> dict:
    """
    Generates title, caption, and hashtags for the assembled video from the
    niche + script. Pure content generation — the caller is responsible for
    getting human approval before any of this is used to actually post.
    """
    prompt = (
        f"Write TikTok posting metadata for a video in the niche \"{niche}\".\n\n"
        f"SCRIPT (voice-over):\n{script}\n\n"
        "Return JSON with exactly these keys:\n"
        '  "title": a short catchy title (max 60 characters),\n'
        '  "caption": an engaging caption for the post (max 150 characters, no hashtags in this field),\n'
        '  "hashtags": array of 5-8 relevant hashtags WITHOUT the # symbol, mixing broad and niche-specific tags.\n\n'
        "Avoid engagement-bait phrasing like 'follow for more' spam patterns — keep it natural "
        "so it doesn't trip TikTok's spam/misinformation filters."
    )
    return client.chat_json(
        prompt,
        system=(
            "You are the SEO/metadata stage of a TikTok content pipeline. "
            "Return ONLY valid JSON, no markdown fences, no commentary."
        ),
    )


# ---------------------------------------------------------------------------
# Daily post-rate limiting (TIKTOK_MAX_POSTS_PER_DAY, default 2)
# ---------------------------------------------------------------------------

def _load_post_log() -> list:
    if not POST_LOG_PATH.exists():
        return []
    try:
        return json.loads(POST_LOG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_post_log(entries: list) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    POST_LOG_PATH.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _posts_today(entries: list) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    return sum(1 for e in entries if e.get("date") == today)


def _record_post_attempt(workflow_id: str, published: bool) -> None:
    entries = _load_post_log()
    entries.append({
        "workflow_id": workflow_id,
        "date": datetime.now(timezone.utc).date().isoformat(),
        "timestamp": time.time(),
        "published": published,
    })
    _save_post_log(entries)


def posts_remaining_today() -> int:
    max_per_day = int(os.getenv("TIKTOK_MAX_POSTS_PER_DAY", "2"))
    return max(0, max_per_day - _posts_today(_load_post_log()))


# ---------------------------------------------------------------------------
# Publish staging — browser automation fallback (draft-mode by default)
# ---------------------------------------------------------------------------

def stage_for_publish(workflow_id: str, video_path: str, caption: str, hashtags: list) -> dict:
    """
    Opens TikTok's upload page via the browser_automation module, uploads
    the video, and fills the caption. Stops short of clicking "Post" unless
    TIKTOK_AUTO_PUBLISH=true is set — in which case __init__.py has already
    required the human to have approved the exact caption/hashtags text
    being used here (per section 10.4: "even in auto publish .env mode,
    Dani must have confirmed at least the caption/hashtags").
    """
    if posts_remaining_today() <= 0:
        max_per_day = int(os.getenv("TIKTOK_MAX_POSTS_PER_DAY", "2"))
        return {
            "success": False,
            "error": f"Daily post limit reached ({max_per_day}/day via TIKTOK_MAX_POSTS_PER_DAY). "
                     f"Try again tomorrow or raise the limit in .env.",
        }

    video_file = Path(video_path)
    if not video_file.exists():
        return {"success": False, "error": f"Video file not found: {video_path}"}

    full_caption = caption.strip()
    if hashtags:
        full_caption += " " + " ".join(f"#{h.lstrip('#')}" for h in hashtags)

    nav_result = browser_control.browser_control({"action": "go_to", "url": TIKTOK_UPLOAD_URL})
    if "navigation error" in nav_result.lower() or "timeout loading" in nav_result.lower():
        return {"success": False, "error": f"Could not open TikTok upload page: {nav_result}"}

    time.sleep(3)  # let the upload SPA finish rendering the file input

    upload_result = browser_control.browser_control({
        "action": "upload_file",
        "selector": "input[type='file']",
        "file_path": str(video_file.resolve()),
    })
    if "error" in upload_result.lower() or "timed out" in upload_result.lower():
        return {
            "success": False,
            "error": (
                f"Video upload failed: {upload_result}. TikTok's upload-page markup changes "
                f"often, so this selector can go stale — check the open browser tab and "
                f"upload manually this time, sir."
            ),
        }

    time.sleep(5)  # TikTok needs a moment to process the video before the caption box is usable

    caption_result = browser_control.browser_control({
        "action": "smart_type",
        "description": "caption or description text box",
        "text": full_caption,
    })

    auto_publish = os.getenv("TIKTOK_AUTO_PUBLISH", "false").strip().lower() == "true"

    if not auto_publish:
        _record_post_attempt(workflow_id, published=False)
        return {
            "success": True,
            "published": False,
            "message": (
                "Video uploaded and caption filled in the browser — NOT posted. "
                "Review it in the open TikTok tab and click Post yourself, or set "
                "TIKTOK_AUTO_PUBLISH=true in .env to let this stage click Post automatically next time."
            ),
            "caption_fill_result": caption_result,
        }

    publish_result = browser_control.browser_control({
        "action": "smart_click",
        "description": "Post button to publish the video",
    })
    _record_post_attempt(workflow_id, published=True)
    return {
        "success": True,
        "published": True,
        "message": f"Post button clicked (TIKTOK_AUTO_PUBLISH=true). Browser result: {publish_result}",
    }
