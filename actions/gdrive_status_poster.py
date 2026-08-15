# actions/gdrive_status_poster.py
"""
Google Drive → WhatsApp Status auto-poster.

Watches a Google Drive folder in the background. Whenever a new product
(image/video + matching text-details file) appears, Jarvis downloads it,
parses the details, and posts it to WhatsApp Status — media on top,
description (name/brand/size/price) as the caption — one product at a time.

ONE-TIME PERMISSION MODEL:
  The user approves monitoring exactly once via `gdrive_status_start`.
  That approval is persisted to memory/gdrive_watch_state.json. On every
  future Jarvis boot, `autostart_if_enabled()` (called from main.py) reads
  that flag and silently resumes the background watch loop — no repeated
  prompts, ever. To turn it off, the user must explicitly say so
  (`gdrive_status_stop`).

VERIFIED-EXECUTION PRINCIPLE (per project convention — see facebook_poster.py):
  A product is only marked "processed" in memory/gdrive_processed_products.json
  after the WhatsApp Status post function actually returns success=True.
  Failed posts are retried on the next poll cycle, never silently marked done.

WHATSAPP STATUS AUTOMATION NOTE:
  send_message.py only sends text DMs today — there is no existing
  "attach media + post to Status" flow in this repo. `_post_whatsapp_status()`
  below implements a best-effort pyautogui/pywinauto flow for the WhatsApp
  Desktop app (Windows). Screen layouts vary by WhatsApp version/DPI/theme,
  so treat WHATSAPP_STATUS_STEPS below as a first pass that will likely need
  on-machine calibration (see comments inline) before it's fully reliable.
"""

import json
import re
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pyautogui
import pywinauto

from core.paths import BASE_DIR
from core.files import atomic_write_text, restrict_permissions, quarantine_corrupt_file

# --------------------------------------------------------------------------- #
# Paths / constants
# --------------------------------------------------------------------------- #

CONFIG_PATH          = BASE_DIR / "config" / "gdrive_status_config.json"
STATE_PATH            = BASE_DIR / "memory" / "gdrive_watch_state.json"
PROCESSED_LOG_PATH    = BASE_DIR / "memory" / "gdrive_processed_products.json"
TEMP_DOWNLOAD_DIR     = BASE_DIR / "temp" / "gdrive_status_downloads"
LOG_PATH              = BASE_DIR / "logs" / "gdrive_whatsapp_status.log"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

DEFAULT_CONFIG = {
    # PLACEHOLDER — paste your Google Drive folder link/ID here before
    # calling gdrive_status_start. Right-click folder in Drive -> "Get
    # link" -> the ID is the part after /folders/ in the URL.
    "gdrive_folder_id": "<< PASTE YOUR GOOGLE DRIVE FOLDER LINK / ID HERE >>",

    # Service account JSON key (recommended — no repeated login prompts).
    # Create one in Google Cloud Console -> IAM & Admin -> Service Accounts
    # -> Keys -> Add key (JSON), then share the Drive folder with the
    # service account's email address (Viewer access is enough).
    "gdrive_service_account_path": "config/gdrive_service_account.json",

    "poll_interval_seconds": 300,
    "delay_between_posts_seconds": 60,
    "max_retries": 2,
    "video_max_duration_seconds": 30,
    "folder_mode": "auto",   # "flat" | "subfolder" | "auto"
}

_watch_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #

def _log(msg: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass
    print(f"[GDriveStatus] {msg}")


# --------------------------------------------------------------------------- #
# Config / state / processed-log — plain JSON, consistent with core/config.py
# --------------------------------------------------------------------------- #

def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        _log(f"⚠️ Could not read {path.name}: {e}")
        quarantine_corrupt_file(path, "GDriveStatus")
        return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))
    restrict_permissions(path)


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(_load_json(CONFIG_PATH, {}))
    if not CONFIG_PATH.exists():
        _save_json(CONFIG_PATH, cfg)
        _log(f"📝 Created default config at {CONFIG_PATH} — fill in gdrive_folder_id.")
    return cfg


def load_state() -> dict:
    return _load_json(STATE_PATH, {"enabled": False, "last_checked_timestamp": None})


def save_state(**updates) -> dict:
    state = load_state()
    state.update(updates)
    _save_json(STATE_PATH, state)
    return state


def load_processed() -> list:
    return _load_json(PROCESSED_LOG_PATH, [])


def mark_processed(drive_file_id: str, product_name: str) -> None:
    entries = load_processed()
    entries.append({
        "drive_file_id": drive_file_id,
        "product_name": product_name,
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "status": "posted",
    })
    _save_json(PROCESSED_LOG_PATH, entries)


def is_processed(drive_file_id: str) -> bool:
    return any(e.get("drive_file_id") == drive_file_id for e in load_processed())


# --------------------------------------------------------------------------- #
# Google Drive access
# --------------------------------------------------------------------------- #

def _get_drive_service(cfg: dict):
    """
    Builds an authenticated Drive API client using a service-account key.
    Requires: google-api-python-client, google-auth
    """
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    key_path = BASE_DIR / cfg["gdrive_service_account_path"]
    if not key_path.exists():
        raise RuntimeError(
            f"Service account key not found at {key_path}. "
            f"Create one in Google Cloud Console and share your Drive "
            f"folder with its email (Viewer access)."
        )

    creds = service_account.Credentials.from_service_account_file(
        str(key_path),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds)


def _list_new_files(service, folder_id: str, since_iso: Optional[str]) -> list:
    """
    Lists files in folder_id modified after since_iso (or everything on
    first run). Includes subfolders one level deep (for folder_mode ==
    'subfolder' / 'auto').
    """
    q_parts = [f"'{folder_id}' in parents", "trashed = false"]
    if since_iso:
        q_parts.append(f"modifiedTime > '{since_iso}'")
    query = " and ".join(q_parts)

    files = []
    page_token = None
    while True:
        resp = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, createdTime, size, parents)",
            orderBy="createdTime",
            pageToken=page_token,
        ).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    # One level of subfolders, for folder_mode == subfolder/auto.
    subfolder_q = (
        f"'{folder_id}' in parents and trashed = false "
        f"and mimeType = 'application/vnd.google-apps.folder'"
    )
    subfolders = service.files().list(
        q=subfolder_q, fields="files(id, name)"
    ).execute().get("files", [])

    for sub in subfolders:
        q_parts = [f"'{sub['id']}' in parents", "trashed = false"]
        if since_iso:
            q_parts.append(f"modifiedTime > '{since_iso}'")
        sub_query = " and ".join(q_parts)
        page_token = None
        while True:
            resp = service.files().list(
                q=sub_query,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, createdTime, size, parents)",
                orderBy="createdTime",
                pageToken=page_token,
            ).execute()
            for f in resp.get("files", []):
                f["_subfolder_name"] = sub["name"]
                files.append(f)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    return files


def _download_file(service, file_id: str, dest_path: Path) -> bool:
    from googleapiclient.http import MediaIoBaseDownload
    import io

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    data = buf.getvalue()
    if not data:
        return False
    dest_path.write_bytes(data)
    return True


# --------------------------------------------------------------------------- #
# Product grouping (flat filename-pair mode OR subfolder mode)
# --------------------------------------------------------------------------- #

def _group_into_products(files: list) -> list:
    """
    Returns a list of product dicts:
      { "name": str, "media_file": {...} | None, "text_file": {...} | None }
    Groups by _subfolder_name when present (subfolder mode), otherwise by
    matching base filename (flat mode).
    """
    subfolder_groups: dict = {}
    flat_groups: dict = {}

    for f in files:
        name = f["name"]
        ext = Path(name).suffix.lower()
        is_media = ext in MEDIA_EXTENSIONS
        is_text = ext == ".txt"
        if not (is_media or is_text):
            continue  # ignore junk files silently, per spec

        if f.get("_subfolder_name"):
            key = f["_subfolder_name"]
            group = subfolder_groups.setdefault(key, {"name": key, "media_file": None, "text_file": None})
        else:
            key = Path(name).stem
            group = flat_groups.setdefault(key, {"name": key, "media_file": None, "text_file": None})

        if is_media:
            group["media_file"] = f
        else:
            group["text_file"] = f

    products = list(subfolder_groups.values()) + list(flat_groups.values())
    # Drop text-only groups (nothing to post) — keep media-only (fallback caption).
    products = [p for p in products if p["media_file"] is not None]
    return products


def _parse_details_text(text: str) -> dict:
    """Parses simple 'Key: Value' lines into an ordered dict."""
    details = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key and value:
            details[key] = value
    return details


def _compose_caption(product_name: str, details: dict) -> str:
    if not details:
        return product_name
    lines = []
    name = details.pop("Name", product_name)
    lines.append(name)
    for k, v in details.items():
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# WhatsApp Status posting (Windows desktop app — pyautogui/pywinauto)
# --------------------------------------------------------------------------- #

WHATSAPP_STATUS_STEPS = """
NOTE FOR CALIBRATION (do this once on Dani's machine before relying on it):
  WhatsApp Desktop's Status tab UI is not exposed via reliable pywinauto
  automation IDs on most builds, so this uses a hybrid approach:
    1. Open WhatsApp Desktop (win search, same as send_message.py's _open_app).
    2. pywinauto.Application(backend="uia").connect(title_re="WhatsApp")
       to get the window handle, then click the "Status" tab in the left
       nav (coordinates vary by window size — capture once with
       pyautogui.position() while hovering, store in config as
       status_tab_x / status_tab_y, or switch to image-based matching
       with pyautogui.locateOnScreen() using a saved icon screenshot).
    3. Click "Add Status" (+ camera icon) -> opens native Windows file
       picker -> type the full media path into the picker's filename box
       -> Enter. This part is reliable (native dialog, not custom-drawn).
    4. Wait for the media preview + caption box to render, click into the
       caption box, type the composed caption.
    5. Press Enter / click the green send arrow to post.
  Until step 2's coordinates or an icon template are calibrated for this
  machine, _post_whatsapp_status() below will likely need small tweaks —
  it's built to fail loudly (return success=False with a clear reason)
  rather than silently claim success, per the verified-execution rule.
"""


def _open_whatsapp_desktop() -> bool:
    try:
        pyautogui.press("win")
        time.sleep(0.4)
        pyautogui.write("WhatsApp", interval=0.04)
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(2.5)
        return True
    except Exception as e:
        _log(f"❌ Could not open WhatsApp Desktop: {e}")
        return False


def _post_whatsapp_status(media_path: Path, caption: str, cfg: dict) -> dict:
    """
    Returns {"success": bool, "error": str|None}. Never claims success
    without getting through the whole flow.
    """
    try:
        if not _open_whatsapp_desktop():
            return {"success": False, "error": "Could not open WhatsApp Desktop"}

        # Connect to the window so we can find/click the Status tab.
        try:
            app = pywinauto.Application(backend="uia").connect(title_re=".*WhatsApp.*", timeout=10)
            win = app.top_window()
            win.set_focus()
        except Exception as e:
            return {"success": False, "error": f"Could not find WhatsApp window: {e}"}

        # --- Status tab click ---
        # Coordinates below are placeholders (status_tab_x/y in config).
        # Calibrate once: hover mouse over the Status tab, run
        # `python -c "import pyautogui,time; time.sleep(3); print(pyautogui.position())"`
        # then set these two config keys.
        status_x = cfg.get("status_tab_x")
        status_y = cfg.get("status_tab_y")
        if status_x is None or status_y is None:
            return {
                "success": False,
                "error": (
                    "status_tab_x/status_tab_y not calibrated in "
                    f"{CONFIG_PATH.name} — see WHATSAPP_STATUS_STEPS in "
                    "actions/gdrive_status_poster.py for how to capture them."
                ),
            }
        pyautogui.click(status_x, status_y)
        time.sleep(1.0)

        add_status_x = cfg.get("add_status_x")
        add_status_y = cfg.get("add_status_y")
        if add_status_x is None or add_status_y is None:
            return {
                "success": False,
                "error": "add_status_x/add_status_y not calibrated in config.",
            }
        pyautogui.click(add_status_x, add_status_y)
        time.sleep(1.5)

        # Native file picker — reliable to drive via keyboard.
        pyautogui.write(str(media_path.resolve()), interval=0.02)
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(2.0)  # media preview render time

        # Caption box — click a relative offset below the preview if a
        # dedicated coordinate isn't set; otherwise Tab into it.
        caption_x = cfg.get("caption_box_x")
        caption_y = cfg.get("caption_box_y")
        if caption_x is not None and caption_y is not None:
            pyautogui.click(caption_x, caption_y)
        else:
            pyautogui.press("tab")
        time.sleep(0.3)
        pyautogui.write(caption, interval=0.02)
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(1.5)

        return {"success": True, "error": None}

    except Exception as e:
        return {"success": False, "error": str(e)}


# --------------------------------------------------------------------------- #
# Video duration guard (uses ffmpeg, already a project dependency)
# --------------------------------------------------------------------------- #

def _get_video_duration_seconds(path: Path) -> Optional[float]:
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def _trim_video_if_needed(path: Path, max_duration: int) -> Path:
    duration = _get_video_duration_seconds(path)
    if duration is None or duration <= max_duration:
        return path
    import subprocess
    trimmed_path = path.with_name(path.stem + "_trimmed" + path.suffix)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(path), "-t", str(max_duration),
             "-c", "copy", str(trimmed_path)],
            capture_output=True, timeout=60,
        )
        if trimmed_path.exists():
            _log(f"✂️ Trimmed video to {max_duration}s: {trimmed_path.name}")
            return trimmed_path
    except Exception as e:
        _log(f"⚠️ Trim failed, posting original length: {e}")
    return path


# --------------------------------------------------------------------------- #
# Core poll cycle
# --------------------------------------------------------------------------- #

def run_poll_cycle() -> dict:
    """
    Runs exactly one detect -> process -> post cycle. Returns a summary
    dict. Safe to call manually (gdrive_status_now) or from the loop.
    """
    cfg = load_config()
    folder_id = cfg.get("gdrive_folder_id", "")
    if not folder_id or folder_id.startswith("<<"):
        msg = "gdrive_folder_id not set in config/gdrive_status_config.json"
        _log(f"⚠️ {msg}")
        return {"success": False, "error": msg, "posted": 0}

    try:
        service = _get_drive_service(cfg)
    except Exception as e:
        _log(f"❌ Drive auth failed: {e}")
        return {"success": False, "error": str(e), "posted": 0}

    state = load_state()
    since_iso = state.get("last_checked_timestamp")

    try:
        files = _list_new_files(service, folder_id, since_iso)
    except Exception as e:
        _log(f"❌ Drive list failed: {e}")
        return {"success": False, "error": str(e), "posted": 0}

    products = _group_into_products(files)
    new_products = [p for p in products if not is_processed(p["media_file"]["id"])]

    if not new_products:
        save_state(last_checked_timestamp=datetime.now(timezone.utc).isoformat())
        return {"success": True, "error": None, "posted": 0}

    posted_count = 0
    for product in new_products:
        media_meta = product["media_file"]
        text_meta = product.get("text_file")
        product_name = product["name"]

        media_ext = Path(media_meta["name"]).suffix.lower()
        local_media_path = TEMP_DOWNLOAD_DIR / f"{media_meta['id']}{media_ext}"

        ok = False
        for attempt in range(1, cfg.get("max_retries", 2) + 2):
            try:
                if not _download_file(service, media_meta["id"], local_media_path):
                    raise RuntimeError("Downloaded 0 bytes")
                # Verify size matches Drive metadata, when available.
                expected_size = media_meta.get("size")
                if expected_size and local_media_path.stat().st_size != int(expected_size):
                    raise RuntimeError("Downloaded size mismatch — partial/corrupt download")
                ok = True
                break
            except Exception as e:
                _log(f"⚠️ Download attempt {attempt} failed for {product_name}: {e}")
                time.sleep(3)

        if not ok:
            _log(f"❌ Giving up on {product_name} — download kept failing.")
            continue

        details = {}
        if text_meta:
            try:
                buf_path = TEMP_DOWNLOAD_DIR / f"{text_meta['id']}.txt"
                if _download_file(service, text_meta["id"], buf_path):
                    details = _parse_details_text(buf_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception as e:
                _log(f"⚠️ Could not read details file for {product_name}: {e}")
        else:
            _log(f"⚠️ No details .txt for {product_name} — posting with fallback caption.")

        if media_ext in VIDEO_EXTENSIONS:
            local_media_path = _trim_video_if_needed(
                local_media_path, cfg.get("video_max_duration_seconds", 30)
            )

        caption = _compose_caption(product_name, details)

        post_result = None
        for attempt in range(1, cfg.get("max_retries", 2) + 2):
            post_result = _post_whatsapp_status(local_media_path, caption, cfg)
            if post_result.get("success"):
                break
            _log(f"⚠️ Post attempt {attempt} failed for {product_name}: {post_result.get('error')}")
            time.sleep(5)

        if post_result and post_result.get("success"):
            mark_processed(media_meta["id"], product_name)
            posted_count += 1
            _log(f"✅ Posted to Status: {product_name}")
        else:
            _log(f"❌ Skipped (never succeeded): {product_name} — "
                 f"{post_result.get('error') if post_result else 'unknown error'}")
            continue  # do not mark processed — retried next cycle

        time.sleep(cfg.get("delay_between_posts_seconds", 60))

    save_state(last_checked_timestamp=datetime.now(timezone.utc).isoformat())
    return {"success": True, "error": None, "posted": posted_count}


# --------------------------------------------------------------------------- #
# Background loop / lifecycle
# --------------------------------------------------------------------------- #

def _watch_loop():
    _log("🟢 Background watch loop started.")
    while not _stop_event.is_set():
        state = load_state()
        if not state.get("enabled"):
            _log("⏸️ Watch disabled — stopping loop.")
            return
        try:
            result = run_poll_cycle()
            if result.get("posted"):
                _log(f"📊 Cycle complete — {result['posted']} product(s) posted.")
        except Exception as e:
            _log(f"❌ Unhandled error in poll cycle: {e}")

        cfg = load_config()
        interval = cfg.get("poll_interval_seconds", 300)
        _stop_event.wait(interval)


def start_watch(parameters: dict = None, player=None) -> str:
    """
    ONE-TIME approval entry point. Sets enabled=true (persisted) and
    starts the background thread. Safe to call again later (e.g. after
    gdrive_status_stop) — it will NOT ask for permission again, per spec.
    """
    global _watch_thread
    save_state(enabled=True)
    _stop_event.clear()

    if _watch_thread is None or not _watch_thread.is_alive():
        _watch_thread = threading.Thread(target=_watch_loop, daemon=True)
        _watch_thread.start()

    cfg = load_config()
    if cfg.get("gdrive_folder_id", "").startswith("<<"):
        msg = (
            "Monitoring activated, but gdrive_folder_id is still a "
            f"placeholder — edit {CONFIG_PATH} with your real Drive "
            "folder ID before it can find anything."
        )
    else:
        msg = "Google Drive monitoring started. New products will post to WhatsApp Status automatically."
    if player:
        player.write_log(f"[gdrive_status] {msg}")
    _log(msg)
    return msg


def stop_watch(parameters: dict = None, player=None) -> str:
    save_state(enabled=False)
    _stop_event.set()
    msg = "Google Drive monitoring stopped."
    _log(msg)
    if player:
        player.write_log(f"[gdrive_status] {msg}")
    return msg


def trigger_poll_now(parameters: dict = None, player=None) -> str:
    result = run_poll_cycle()
    if not result.get("success"):
        return f"Poll failed: {result.get('error')}"
    n = result.get("posted", 0)
    return f"Checked Drive now — {n} new product(s) posted to Status." if n else "Checked Drive now — nothing new."


def get_watch_status(parameters: dict = None, player=None) -> str:
    state = load_state()
    processed = load_processed()
    enabled = state.get("enabled", False)
    last = state.get("last_checked_timestamp", "never")
    return (
        f"Monitoring is {'ON' if enabled else 'OFF'}. "
        f"Last checked: {last}. Total products posted so far: {len(processed)}."
    )


def autostart_if_enabled() -> None:
    """
    Call this once from main.py at boot (before ui.root.mainloop()).
    Resumes the background watch loop silently if the user previously
    approved it — NEVER prompts again.
    """
    state = load_state()
    if state.get("enabled"):
        _log("🔄 Resuming Google Drive watch from previous session (no prompt — already approved).")
        global _watch_thread
        _stop_event.clear()
        _watch_thread = threading.Thread(target=_watch_loop, daemon=True)
        _watch_thread.start()


# --------------------------------------------------------------------------- #
# TOOL_DECLARATIONS — merged into main.py's Gemini function-calling schema
# --------------------------------------------------------------------------- #

TOOL_DECLARATIONS = [
    {
        "name": "gdrive_status_start",
        "description": (
            "Starts (or resumes) automatic monitoring of the configured Google "
            "Drive folder for new products (photo/video + details text file), "
            "posting each one to WhatsApp Status automatically. This is a "
            "ONE-TIME setup — call it when the user explicitly asks to begin "
            "auto-posting new Drive products to Status ('Jarvis, naya data "
            "Drive pe WhatsApp status pe automatically lagao', 'shuru karo "
            "status posting'). Once started, it keeps running in the "
            "background across restarts — never ask for this permission again "
            "after the first successful start."
        ),
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "gdrive_status_stop",
        "description": (
            "Stops the automatic Google Drive to WhatsApp Status monitoring. "
            "Call this ONLY when the user explicitly asks to stop/pause it "
            "('status posting band karo')."
        ),
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "gdrive_status_now",
        "description": (
            "Immediately checks the Google Drive folder for new products and "
            "posts any found to WhatsApp Status right now, instead of waiting "
            "for the next scheduled background check. Use when the user says "
            "something like 'Jarvis, naya data daala hai, abhi check karo'."
        ),
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "gdrive_status_status",
        "description": (
            "Reports whether Google Drive -> WhatsApp Status monitoring is "
            "currently on or off, when it last checked, and how many products "
            "have been posted in total. Use for 'kitne products post ho chuke "
            "hain' / 'status monitoring on hai kya' type questions."
        ),
        "parameters": {"type": "OBJECT", "properties": {}},
    },
]
