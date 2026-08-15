# actions/facebook_poster.py
"""
Facebook Page posting via the Meta Graph API.

Implements the workflow documented in facebook.md:
  - Section 6:  Posting via Meta Graph API
  - Section 7:  Credential setup (config/api_keys.json)
  - Section 8:  Database update / duplicate prevention
  - Section 9:  Success reporting
  - Section 10: Failure handling

VERIFIED-EXECUTION PRINCIPLE (per project convention):
  This module NEVER reports success unless the Meta Graph API actually
  returned a real `post_id` in its response. No narrative/LLM-fabricated
  success messages — only what the API confirms.
"""

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from core.config import get_facebook_page_access_token, get_facebook_page_id
from core.files import atomic_write_text, restrict_permissions
from core.paths import BASE_DIR

GRAPH_API_VERSION = "v19.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
GRAPH_VIDEO_URL = f"https://graph-video.facebook.com/{GRAPH_API_VERSION}"

POSTS_LOG_PATH = BASE_DIR / "memory" / "facebook_posts.json"
DUPLICATE_WINDOW_HOURS = 24

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = [30, 120, 300]  # 30s, 2min, 5min


# --------------------------------------------------------------------------- #
# Local post log (Section 8: Database Update / Duplicate Prevention)
# --------------------------------------------------------------------------- #

def _load_posts_log() -> list:
    if not POSTS_LOG_PATH.exists():
        return []
    try:
        data = json.loads(POSTS_LOG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        print(f"[FacebookPoster] ⚠️ Could not read posts log: {e}")
        return []


def _save_posts_log(entries: list) -> None:
    POSTS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(POSTS_LOG_PATH, json.dumps(entries, indent=4, ensure_ascii=False))
    restrict_permissions(POSTS_LOG_PATH)


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_recent_duplicate(file_hash: str, page_id: str) -> dict | None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DUPLICATE_WINDOW_HOURS)
    for entry in _load_posts_log():
        if entry.get("file_hash") != file_hash or entry.get("page_id") != page_id:
            continue
        if entry.get("status") != "success":
            continue
        try:
            published = datetime.fromisoformat(entry.get("published_time", ""))
        except ValueError:
            continue
        if published >= cutoff:
            return entry
    return None


def _log_post(
    *,
    status: str,
    page_id: str,
    media_path: str,
    file_hash: str,
    caption: str,
    post_id: str | None = None,
    error: str | None = None,
    scheduled_time: str | None = None,
) -> None:
    entries = _load_posts_log()
    entries.append({
        "post_id":        post_id,
        "page_id":        page_id,
        "media_path":     media_path,
        "file_hash":      file_hash,
        "caption":        caption,
        "scheduled_time": scheduled_time,
        "published_time": datetime.now(timezone.utc).isoformat(),
        "status":         status,      # "success" | "failed"
        "error":          error,
    })
    _save_posts_log(entries)


# --------------------------------------------------------------------------- #
# Caption generation (Step 3.3) — used only when caller doesn't supply one
# --------------------------------------------------------------------------- #

def _generate_caption(media_path: Path, context: str = "") -> str:
    try:
        from core.gemini import get_generative_model
        model = get_generative_model("gemini-2.5-flash")
        prompt = (
            "Write a short, engaging, viral-style Facebook caption "
            "(2-3 sentences, include 3-5 relevant hashtags at the end) "
            f"for a post about: {context or media_path.stem}. "
            "Output ONLY the caption text, nothing else."
        )
        response = model.generate_content(prompt)
        caption = response.text.strip()
        if caption:
            return caption
    except Exception as e:
        print(f"[FacebookPoster] ⚠️ Caption generation failed: {e}")

    # Deterministic fallback — never block a post just because caption-gen failed.
    return f"{media_path.stem} #Velmora"


# --------------------------------------------------------------------------- #
# Graph API calls (Section 6)
# --------------------------------------------------------------------------- #

def _post_photo(page_id: str, token: str, media_path: Path, caption: str,
                 published: bool, scheduled_unix: int | None) -> dict:
    url = f"{GRAPH_BASE_URL}/{page_id}/photos"
    data = {"caption": caption, "access_token": token, "published": str(published).lower()}
    if scheduled_unix:
        data["scheduled_publish_time"] = scheduled_unix
    with open(media_path, "rb") as f:
        resp = requests.post(url, data=data, files={"source": f}, timeout=120)
    return resp.json(), resp.status_code


def _post_video(page_id: str, token: str, media_path: Path, caption: str,
                 published: bool, scheduled_unix: int | None) -> dict:
    url = f"{GRAPH_VIDEO_URL}/{page_id}/videos"
    data = {"description": caption, "access_token": token, "published": str(published).lower()}
    if scheduled_unix:
        data["scheduled_publish_time"] = scheduled_unix
    with open(media_path, "rb") as f:
        resp = requests.post(url, data=data, files={"source": f}, timeout=300)
    return resp.json(), resp.status_code


def _extract_graph_error(response_json: dict) -> str:
    err = response_json.get("error", {})
    return err.get("message") or err.get("type") or "Unknown Graph API error"


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

def facebook_post(parameters: dict, player=None, speak=None) -> str:
    """
    parameters:
        media_path       (str, required)  - local path to photo/video
        caption          (str, optional)  - auto-generated if omitted (Step 3.3)
        page_id          (str, optional)  - defaults to config/api_keys.json fb_page_id
        scheduled_time   (str, optional)  - ISO 8601 timestamp; omit for immediate publish
        force            (bool, optional) - bypass duplicate-post check
    """

    def _report(msg: str) -> str:
        if player:
            try:
                player.write_log(f"JARVIS: {msg}")
            except Exception as e:
                print(f"[FacebookPoster] ⚠️ Could not write to UI log: {e}")
        if speak:
            try:
                speak(msg)
            except Exception as e:
                print(f"[FacebookPoster] ⚠️ Could not speak message: {e}")
        return msg

    media_path_raw = parameters.get("media_path")
    if not media_path_raw:
        return _report("Sir, I need the media file location before I can post — no path was given.")

    media_path = Path(media_path_raw).expanduser()
    if not media_path.exists() or not media_path.is_file():
        return _report(f"Sir, I couldn't find the file at {media_path}. Post not created.")

    ext = media_path.suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        media_type = "video"
    elif ext in PHOTO_EXTENSIONS:
        media_type = "photo"
    else:
        return _report(f"Sir, '{ext}' isn't a supported photo/video format for Facebook.")

    try:
        page_id = parameters.get("page_id") or get_facebook_page_id()
        token = get_facebook_page_access_token()
    except RuntimeError as e:
        return _report(f"Sir, Facebook isn't configured yet: {e}")

    file_hash = _file_hash(media_path)

    if not parameters.get("force"):
        dup = _find_recent_duplicate(file_hash, page_id)
        if dup:
            return _report(
                f"Sir, this exact file was already published to this Page "
                f"(post ID {dup.get('post_id')}) within the last {DUPLICATE_WINDOW_HOURS} hours. "
                f"Skipping to avoid a duplicate post — say 'force post' if this is intentional."
            )

    caption = parameters.get("caption") or _generate_caption(media_path, parameters.get("context", ""))

    scheduled_time = parameters.get("scheduled_time")
    scheduled_unix = None
    published = True
    if scheduled_time:
        try:
            dt = datetime.fromisoformat(scheduled_time)
            scheduled_unix = int(dt.timestamp())
            published = False
        except ValueError:
            return _report(f"Sir, '{scheduled_time}' isn't a valid schedule timestamp. Post not created.")

    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if media_type == "photo":
                result, status_code = _post_photo(page_id, token, media_path, caption, published, scheduled_unix)
            else:
                result, status_code = _post_video(page_id, token, media_path, caption, published, scheduled_unix)

            post_id = result.get("id") or result.get("post_id")

            # VERIFIED-EXECUTION CHECK — no post_id, no success claim.
            if status_code == 200 and post_id:
                _log_post(
                    status="success", page_id=page_id, media_path=str(media_path),
                    file_hash=file_hash, caption=caption, post_id=post_id,
                    scheduled_time=scheduled_time,
                )
                if scheduled_time:
                    return _report(f"Post scheduled for {scheduled_time} on the Page, sir. Post ID: {post_id}.")
                return _report(f"Post successfully published, sir. Post ID: {post_id}. Caption: '{caption[:80]}'")

            last_error = _extract_graph_error(result)
            print(f"[FacebookPoster] ❌ Attempt {attempt} failed: {last_error}")

        except requests.RequestException as e:
            last_error = str(e)
            print(f"[FacebookPoster] ❌ Attempt {attempt} network error: {last_error}")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_SECONDS[attempt - 1])

    _log_post(
        status="failed", page_id=page_id, media_path=str(media_path),
        file_hash=file_hash, caption=caption, error=last_error,
        scheduled_time=scheduled_time,
    )
    return _report(
        f"Sir, the post failed after {MAX_RETRIES} attempts. Reason: {last_error}. "
        f"The file is still available locally if you want to retry manually."
    )
