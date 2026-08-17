import asyncio
import threading
import time
import traceback

import sounddevice as sd
from google.genai import types
from core.config import get_gemini_key
from core.gemini import get_genai_client
from core.paths import PROMPT_PATH, BASE_DIR
from ui import JarvisUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
    should_extract_memory, extract_memory
)

from actions.file_processor import file_processor
from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import screen_process
from actions.youtube_video     import youtube_video
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater
from actions.viral_clipper     import jarvis_tool_cut_viral_clips
from actions.website_builder   import TOOL_DECLARATIONS as website_builder_tools
from actions.website_builder   import jarvis_tool_generate_website
from actions.facebook_poster   import facebook_post
from actions.screen_recorder   import TOOL_DECLARATIONS as screen_recorder_tools
from actions.screen_recorder   import start_recording, stop_recording, get_recording_status
from actions.tiktok_pipeline   import TOOL_DECLARATIONS as tiktok_pipeline_tools
from actions.tiktok_pipeline   import (
    start_tiktok_workflow, get_tiktok_status, continue_tiktok_workflow,
    finalize_tiktok_video, publish_tiktok_video,
)
from actions.claude_agent      import TOOL_DECLARATIONS as claude_agent_tools
from actions.claude_agent      import ask_claude_action
from actions.gdrive_status_poster import TOOL_DECLARATIONS as gdrive_status_tools
from actions.gdrive_status_poster import (
    start_watch as gdrive_status_start,
    stop_watch as gdrive_status_stop,
    trigger_poll_now as gdrive_status_now,
    get_watch_status as gdrive_status_status,
    autostart_if_enabled as gdrive_status_autostart_if_enabled,
)

from core.skill_registry       import build_registry, prompt_block, read_doc
from core.mcp_manager           import McpManager  # MCP INTEGRATION


LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024


# System prompt + skill-registry scan (AST-parses every module in actions/
# and agent/) are expensive, so they are cached: rebuilt at most once per
# _PROMPT_CACHE_TTL seconds, or immediately when the prompt file changes.
# Memory stays per-connect (it changes far more often than code/docs).
_PROMPT_CACHE_TTL = 300  # seconds
_prompt_cache: dict = {"text": None, "built_at": 0.0, "mtime": None}


def _load_system_prompt() -> str:
    try:
        mtime = PROMPT_PATH.stat().st_mtime
    except OSError:
        mtime = None

    if (
        _prompt_cache["text"] is not None
        and _prompt_cache["mtime"] == mtime
        and time.monotonic() - _prompt_cache["built_at"] < _PROMPT_CACHE_TTL
    ):
        return _prompt_cache["text"]

    try:
        prompt = PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[JARVIS] ⚠️ Could not read {PROMPT_PATH}: {e} — using built-in prompt")
        prompt = (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )

    # Registry ko rebuild karo (naye modules/docs khud detect ho jayenge)
    # aur uska summary system prompt ke saath jod do, taake Jarvis kisi bhi request
    # ka jawab dene se pehle registry check kar sake.
    try:
        registry = build_registry()
        prompt += prompt_block(registry)
        print(f"[Registry] ✅ {len(registry['modules'])} modules, {len(registry['docs'])} docs loaded")
    except Exception as e:
        print(f"[Registry] ⚠️ Could not build skill registry: {e}")

    _prompt_cache.update(text=prompt, built_at=time.monotonic(), mtime=mtime)
    return prompt
    
_last_memory_input = ""

def _update_memory_async(user_text: str, jarvis_text: str) -> None:
    global _last_memory_input

    user_text   = (user_text   or "").strip()
    jarvis_text = (jarvis_text or "").strip()

    if len(user_text) < 5 or user_text == _last_memory_input:
        return
    _last_memory_input = user_text

    try:
        api_key = get_gemini_key()
        if not should_extract_memory(user_text, jarvis_text, api_key):
            return
        data = extract_memory(user_text, jarvis_text, api_key)
        if data:
            update_memory(data)
            print(f"[Memory] ✅ {list(data.keys())}")
    except Exception as e:
        if "429" not in str(e):
            print(f"[Memory] ⚠️ {e}")

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application on the computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it. "
            "If the user asks to open a specific chat/contact inside a messaging app "
            "(e.g. 'bhalu ki chat open karo', 'open my chat with Bhalu on WhatsApp'), "
            "still call this tool with app_name set to the messaging app and also pass "
            "chat_name set to the contact's name — do not just open the app generically."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
                },
                "chat_name": {
                    "type": "STRING",
                    "description": (
                        "Optional. Name of the contact/chat to open directly inside a "
                        "messaging app such as WhatsApp or Telegram (e.g. 'Bhalu'). "
                        "Leave empty if the user just wants the app itself opened."
                    )
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "facebook_post",
        "description": (
            "Publishes a post to a Facebook Page via the Meta Graph API — text-only, "
            "photo, or video. ALWAYS use this for any Facebook Page posting request "
            "(text or media) — NEVER route Facebook posting through agent_task or "
            "browser_control, since only this tool verifies a real post_id from the API "
            "before reporting success. NEVER tell the user a post succeeded (or is in "
            "progress) without having actually called this tool and read its returned "
            "result — the returned string is the ONLY source of truth for success/failure. "
            "For a text-only post, set post_type='text' and text_content to the exact "
            "wording the user gave; no media_path is needed. For a photo/video post, set "
            "post_type='photo' or 'video' and media_path to an actual local file path — "
            "never invent or guess one; ask the user for the file/Drive location first if "
            "it wasn't given, and only call this tool once you have it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "post_type":      {"type": "STRING",  "description": "'text', 'photo', or 'video'. Required — infer from the request (no file mentioned = 'text')."},
                "text_content":   {"type": "STRING",  "description": "The exact text to post. Required when post_type is 'text'."},
                "media_path":     {"type": "STRING",  "description": "Local path to the photo or video file to post. Required when post_type is 'photo' or 'video'."},
                "page_name":      {"type": "STRING",  "description": "Facebook Page display name mentioned by the user, e.g. 'Velmora'. Used for the spoken confirmation."},
                "caption":        {"type": "STRING",  "description": "Post caption/description. Omit to auto-generate."},
                "page_id":        {"type": "STRING",  "description": "Facebook Page ID. Omit to use the configured default Page."},
                "scheduled_time": {"type": "STRING",  "description": "ISO 8601 timestamp to schedule the post. Omit to publish immediately."},
                "context":        {"type": "STRING",  "description": "Short context about the media, used only if auto-generating the caption"},
                "force":          {"type": "BOOLEAN", "description": "Bypass the duplicate-post check (default: false)"},
            },
            "required": ["post_type"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Windows Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controls the web browser. Use for: opening websites, searching the web, "
            "clicking elements, filling forms, scrolling, any web-based task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | press | close"},
                "url":         {"type": "STRING", "description": "URL for go_to action"},
                "query":       {"type": "STRING", "description": "Search query for search action"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type"},
                "text":        {"type": "STRING", "description": "Text to click or type"},
                "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"},
                "direction":   {"type": "STRING", "description": "up or down for scroll"},
                "key":         {"type": "STRING", "description": "Key name for press action"},
                "incognito":   {"type": "BOOLEAN", "description": "Open in private/incognito mode"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders: list, create, delete, move, copy, rename, read, write, find, disk usage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, clean, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: auto)"},
                "description": {"type": "STRING", "description": "What the code should do or what change to make"},
                "language":    {"type": "STRING", "description": "Programming language (default: python)"},
                "output_path": {"type": "STRING", "description": "Where to save the file"},
                "file_path":   {"type": "STRING", "description": "Path to existing file for edit/explain/run/build"},
                "code":        {"type": "STRING", "description": "Raw code string for explain"},
                "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
                "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "What the project should do"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use agent_task, browser_control, or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "cut_viral_clips",
        "description": (
            "Kisi bhi EXISTING video (YouTube link ya local file) se AI-detected viral moments cut "
            "karke short clips banata hai, original quality/audio preserve karte hue. "
            "Use whenever the user asks to extract viral clips, highlights, or shorts from a video "
            "THEY ALREADY HAVE OR LINKED. Requires an actual video_source — never guess or invent one. "
            "Do NOT use this when the user wants a brand-new video created from just a topic/niche "
            "with no source video (use start_tiktok_workflow for that instead). "
            "Say two short sentences before calling this tool (it is a slow tool) — result is spoken back automatically."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "video_source": {"type": "STRING",  "description": "Video URL (YouTube etc.) ya local file ka path"},
                "num_clips":    {"type": "INTEGER", "description": "Kitni clips chahiye (default 5)"},
            },
            "required": ["video_source"]
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
    "name": "file_processor",
    "description": (
        "Processes any file that the user has uploaded or dropped onto the interface. "
        "Use this when the user refers to an uploaded file and wants an action on it. "
        "Supports: images (describe/ocr/resize/compress/convert), "
        "PDFs (summarize/extract_text/to_word), "
        "Word docs & text files (summarize/fix/reformat/translate), "
        "CSV/Excel (analyze/stats/filter/sort/convert), "
        "JSON/XML (validate/format/analyze), "
        "code files (explain/review/fix/optimize/run/document/test), "
        "audio (transcribe/trim/convert/info), "
        "video (trim/extract_audio/extract_frame/compress/transcribe/info), "
        "archives (list/extract), "
        "presentations (summarize/extract_text). "
        "ALWAYS call this tool when a file has been uploaded and the user gives a command about it. "
        "If the user's command is ambiguous, pick the most logical action for that file type."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Full path to the uploaded file. Leave empty to use the currently uploaded file."
            },
            "action": {
                "type": "STRING",
                "description": (
                    "What to do with the file. Examples by type:\n"
                    "image: describe | ocr | resize | compress | convert | info\n"
                    "pdf: summarize | extract_text | to_word | info\n"
                    "docx/txt: summarize | fix | reformat | translate_hint | word_count | to_bullet\n"
                    "csv/excel: analyze | stats | filter | sort | convert | info\n"
                    "json: validate | format | analyze | to_csv\n"
                    "code: explain | review | fix | optimize | run | document | test\n"
                    "audio: transcribe | trim | convert | info\n"
                    "video: trim | extract_audio | extract_frame | compress | transcribe | info | convert\n"
                    "archive: list | extract\n"
                    "pptx: summarize | extract_text | analyze"
                )
            },
            "instruction": {
                "type": "STRING",
                "description": "Free-form instruction if action doesn't cover it. E.g. 'translate this to Turkish', 'find all email addresses'"
            },
            "format": {
                "type": "STRING",
                "description": "Target format for conversion. E.g. 'mp3', 'pdf', 'csv', 'png'"
            },
            "width":     {"type": "INTEGER", "description": "Target width for image resize"},
            "height":    {"type": "INTEGER", "description": "Target height for image resize"},
            "scale":     {"type": "NUMBER",  "description": "Scale factor for image resize (e.g. 0.5)"},
            "quality":   {"type": "INTEGER", "description": "Quality 1-100 for image/video compress"},
            "start":     {"type": "STRING",  "description": "Start time for trim: seconds or HH:MM:SS"},
            "end":       {"type": "STRING",  "description": "End time for trim: seconds or HH:MM:SS"},
            "timestamp": {"type": "STRING",  "description": "Timestamp for video frame extraction HH:MM:SS"},
            "column":    {"type": "STRING",  "description": "Column name for CSV filter/sort"},
            "value":     {"type": "STRING",  "description": "Filter value for CSV filter"},
            "condition": {"type": "STRING",  "description": "Filter condition: equals|contains|gt|lt"},
            "ascending": {"type": "BOOLEAN", "description": "Sort order for CSV sort (default: true)"},
            "save":      {"type": "BOOLEAN", "description": "Save result to file (default: true)"},
            "destination": {"type": "STRING", "description": "Output folder for archive extract"},
        },
        "required": []
    }
},
    {
    "name": "shutdown_jarvis",
    "description": (
        "Shuts down the assistant completely. "
        "Call this when the user expresses intent to end the conversation, "
        "close the assistant, say goodbye, or stop Jarvis. "
        "The user can say this in ANY language."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Fatih, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
]

TOOL_DECLARATIONS.append({
    "name": "read_project_doc",
    "description": (
        "Reads the full content of one of Jarvis's own project .md docs (e.g. Modules.md, "
        "Commands.md, Architecture.md, Roadmap.md, Bug.md, Ideas.md, Tasks.md) or the "
        "auto-generated SKILLS_REGISTRY.md. Use this whenever the skill registry summary "
        "already in the system prompt isn't detailed enough to decide how to handle a request, "
        "or when the user asks what a doc/module contains."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "doc_name": {"type": "STRING", "description": "Filename of the .md doc, e.g. 'Modules.md'"}
        },
        "required": ["doc_name"]
    }
})

TOOL_DECLARATIONS.extend(website_builder_tools)
TOOL_DECLARATIONS.extend(screen_recorder_tools)
TOOL_DECLARATIONS.extend(tiktok_pipeline_tools)
TOOL_DECLARATIONS.extend(claude_agent_tools)
TOOL_DECLARATIONS.extend(gdrive_status_tools)


class JarvisLive:

    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self.ui.on_text_command = self._on_text_command
        self.mcp_manager    = McpManager()  # MCP INTEGRATION — config/mcp_servers.json se tools load hote hain
        self._tool_dispatch = self._build_tool_dispatch()

    def _on_text_command(self, text: str):
        self._send_text(text, source="text command")

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            changed = self._is_speaking != value
            self._is_speaking = value
        if not changed:
            return  # playback calls this per audio chunk — only update the UI on transitions
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def speak(self, text: str):
        self._send_text(text, source="speak")

    def _send_text(self, text: str, source: str):
        """Sends text to the live session, reporting instead of dropping failures."""
        if not self._loop or not self.session:
            msg = f"Not connected yet — {source} discarded: {text[:60]}"
            print(f"[JARVIS] ⚠️ {msg}")
            self.ui.write_log(f"ERR: {msg}")
            return

        future = asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

        def _report(fut):
            error = fut.exception()
            if error is not None:
                print(f"[JARVIS] ❌ Failed to send {source}: {error}")
                self.ui.write_log(f"ERR: {source} not delivered — {error}")

        future.add_done_callback(_report)

    def speak_error(self, tool_name: str, error: object):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

    def _build_tool_dispatch(self) -> dict:
        """name -> handler(args) -> result string. Handlers run in a worker thread.

        Built once: a dict lookup replaces the previous ~30-branch if/elif chain,
        so dispatch is O(1) and adding a tool is a one-line change. Built-in tools
        take precedence over MCP-discovered tools on a name collision.
        """
        ui    = self.ui
        speak = self.speak

        def with_current_file(a: dict) -> dict:
            if not a.get("file_path") and ui.current_file:
                a = {**a, "file_path": ui.current_file}
            return a

        def generate_website(a: dict) -> str:
            # Verified-execution tool: report the true pipeline outcome —
            # success only when the production build actually compiled.
            res = jarvis_tool_generate_website(**a)
            if isinstance(res, dict):
                if res.get("success"):
                    return f"Website generated and production build verified at {res.get('project_path', '')}."
                return f"Website generation failed at stage {res.get('stage', '?')}: {res.get('error', res)}"
            return str(res)

        return {
            "open_app":          lambda a: open_app(parameters=a, response=None, player=ui) or f"Opened {a.get('app_name')}.",
            "weather_report":    lambda a: weather_action(parameters=a, player=ui) or "Weather delivered.",
            "browser_control":   lambda a: browser_control(parameters=a, player=ui) or "Done.",
            "file_controller":   lambda a: file_controller(parameters=a, player=ui) or "Done.",
            "send_message":      lambda a: send_message(parameters=a, response=None, player=ui, session_memory=None) or f"Message sent to {a.get('receiver')}.",
            # Verified-execution tool: facebook_post() itself returns the true outcome
            # (success with post_id, or a specific failure reason) — never overridden.
            "facebook_post":     lambda a: facebook_post(parameters=a, player=ui, speak=speak),
            "reminder":          lambda a: reminder(parameters=a, response=None, player=ui) or "Reminder set.",
            "youtube_video":     lambda a: youtube_video(parameters=a, response=None, player=ui) or "Done.",
            "file_processor":    lambda a: file_processor(parameters=with_current_file(a), player=ui, speak=speak) or "Done.",
            "computer_settings": lambda a: computer_settings(parameters=a, response=None, player=ui) or "Done.",
            "desktop_control":   lambda a: desktop_control(parameters=a, player=ui) or "Done.",
            "code_helper":       lambda a: code_helper(parameters=a, player=ui, speak=speak) or "Done.",
            "dev_agent":         lambda a: dev_agent(parameters=a, player=ui, speak=speak) or "Done.",
            "web_search":        lambda a: web_search_action(parameters=a, player=ui) or "Done.",
            "ask_claude":        lambda a: ask_claude_action(parameters=a, player=ui) or "Done.",
            "computer_control":  lambda a: computer_control(parameters=a, player=ui) or "Done.",
            "game_updater":      lambda a: game_updater(parameters=a, player=ui, speak=speak) or "Done.",
            "flight_finder":     lambda a: flight_finder(parameters=a, player=ui) or "Done.",
            "cut_viral_clips":   lambda a: jarvis_tool_cut_viral_clips(
                                             video_source=a["video_source"],
                                             num_clips=a.get("num_clips", 5),
                                         ) or "Done.",
            "generate_website":  generate_website,
            "start_screen_recording":      lambda a: start_recording(parameters=a, player=ui) or "Done.",
            "stop_screen_recording":       lambda a: stop_recording(parameters=a, player=ui) or "Done.",
            "get_screen_recording_status": lambda a: get_recording_status(parameters=a, player=ui) or "Done.",
            "start_tiktok_workflow":       lambda a: start_tiktok_workflow(parameters=a, player=ui) or "Done.",
            "get_tiktok_status":           lambda a: get_tiktok_status(parameters=a, player=ui) or "Done.",
            "continue_tiktok_workflow":    lambda a: continue_tiktok_workflow(parameters=a, player=ui) or "Done.",
            "finalize_tiktok_video":       lambda a: finalize_tiktok_video(parameters=a, player=ui) or "Done.",
            "publish_tiktok_video":        lambda a: publish_tiktok_video(parameters=a, player=ui) or "Done.",
            "gdrive_status_start":  lambda a: gdrive_status_start(parameters=a, player=ui) or "Started.",
            "gdrive_status_stop":   lambda a: gdrive_status_stop(parameters=a, player=ui) or "Stopped.",
            "gdrive_status_now":    lambda a: gdrive_status_now(parameters=a, player=ui) or "Checked.",
            "gdrive_status_status": lambda a: gdrive_status_status(parameters=a, player=ui) or "Done.",
            "read_project_doc":     lambda a: read_doc(a.get("doc_name", "")) or "Doc not found.",
        }

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[JARVIS] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")
        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                print(f"[Memory] 💾 save_memory: {category}/{key} = {value}")
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop   = asyncio.get_running_loop()
        result = "Done."

        try:
            if name == "screen_process":
                def _run_screen_process():
                    try:
                        screen_process(parameters=args, response=None,
                                       player=self.ui, session_memory=None)
                    except Exception as e:
                        traceback.print_exc()
                        self.speak_error("screen_process", e)

                threading.Thread(
                    target=_run_screen_process,
                    daemon=True
                ).start()
                result = "Vision module activated. Stay completely silent — vision module will speak directly."

            elif name == "agent_task":
                from agent.task_queue import get_queue, TaskPriority
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                result   = f"Task started (ID: {task_id})."

            elif name == "shutdown_jarvis":
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Goodbye, sir.")

                def _shutdown():
                    import time, sys, os
                    time.sleep(1)
                    os._exit(0)

                threading.Thread(target=_shutdown, daemon=True).start()

            else:
                handler = self._tool_dispatch.get(name)
                if handler is not None:
                    result = await loop.run_in_executor(None, handler, args)
                elif self.mcp_manager.owns(name):  # MCP INTEGRATION
                    result = await self.mcp_manager.call_tool(name, args)
                else:
                    result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] 📤 {name} → {str(result)[:80]}")

        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    def _enqueue_audio(self, data: bytes) -> None:
        """Queue one mic chunk for sending. When the send buffer is full, drop
        the OLDEST chunk so Gemini always hears fresh audio (realtime prefers
        low latency over losslessness) instead of raising QueueFull inside the
        event loop, which the previous put_nowait() callback did on overflow."""
        q = self.out_queue
        if q is None:
            return
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            q.put_nowait({"data": data, "mime_type": "audio/pcm"})
        except asyncio.QueueFull:
            pass  # lost the race with the consumer — safe to skip one chunk

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _listen_audio(self):
        print("[JARVIS] 🎤 Mic started")
        loop = asyncio.get_running_loop()

        def callback(indata, frames, time_info, status):
            with self._speaking_lock:
                jarvis_speaking = self._is_speaking
            if not jarvis_speaking and not self.ui.muted:
                loop.call_soon_threadsafe(self._enqueue_audio, indata.tobytes())

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                callback=callback,
            ):
                print("[JARVIS] 🎤 Mic stream open")
                await asyncio.Event().wait()  # park until the TaskGroup cancels us
        except Exception as e:
            print(f"[JARVIS] ❌ Mic: {e}")
            raise

    async def _receive_audio(self):
        print("[JARVIS] 👂 Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():

                    if response.data:
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            self.set_speaking(True)
                            txt = sc.output_transcription.text.strip()
                            if txt:
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = sc.input_transcription.text.strip()
                            if txt:
                                in_buf.append(txt)

                        if sc.turn_complete:
                            self.set_speaking(False)

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Jarvis: {full_out}")
                            out_buf = []

                            if full_in and len(full_in) > 5:
                                threading.Thread(
                                    target=_update_memory_async,
                                    args=(full_in, full_out),
                                    daemon=True
                                ).start()

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[JARVIS] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )

        except Exception as e:
            print(f"[JARVIS] ❌ Recv: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[JARVIS] 🔊 Play started")

        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()
        try:
            while True:
                chunk = await self.audio_in_queue.get()
                self.set_speaking(True)
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            print(f"[JARVIS] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def run(self):
        client = get_genai_client(api_version="v1beta")

        # MCP INTEGRATION — ek dafa connect karo, discovered tools ko
        # global TOOL_DECLARATIONS mein merge karo (loop shuru hone se pehle,
        # taake _build_config() inhe turant Gemini ko bhej sake).
        await self.mcp_manager.connect_all()
        TOOL_DECLARATIONS.extend(self.mcp_manager.get_tool_declarations())

        backoff = 3
        while True:
            connected_at = None
            try:
                print("[JARVIS] 🔌 Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_running_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=10)
                    connected_at        = time.monotonic()

                    print("[JARVIS] ✅ Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: JARVIS online.")

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())

            except Exception as e:
                print(f"[JARVIS] ⚠️ {e}")
                traceback.print_exc()

            self.set_speaking(False)
            self.ui.set_state("THINKING")

            # Healthy sessions reset the backoff; rapid repeated failures back
            # off exponentially (3s → 60s cap) instead of hammering the API
            # every 3 seconds forever (e.g. when quota is exhausted).
            if connected_at and time.monotonic() - connected_at > 30:
                backoff = 3
            print(f"[JARVIS] 🔄 Reconnecting in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


def main():
    ui = JarvisUI(str(BASE_DIR / "face.png"))

    # Resumes Google Drive -> WhatsApp Status monitoring silently if it was
    # already approved in a previous session. Never asks permission again.
    gdrive_status_autostart_if_enabled()

    def runner():
        ui.wait_for_api_key()
        jarvis = JarvisLive(ui)
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()
