# actions/open_app.py
# Dani  — Cross-Platform App Launcher

import time
import subprocess
import platform
import shutil

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

_APP_ALIASES = {
    "whatsapp":           {"Windows": "WhatsApp",               "Darwin": "WhatsApp",            "Linux": "https://web.whatsapp.com"},
    "chrome":             {"Windows": "chrome",                 "Darwin": "Google Chrome",       "Linux": "google-chrome"},
    "google chrome":      {"Windows": "chrome",                 "Darwin": "Google Chrome",       "Linux": "google-chrome"},
    "firefox":            {"Windows": "firefox",                "Darwin": "Firefox",             "Linux": "firefox"},
    "spotify":            {"Windows": "Spotify",                "Darwin": "Spotify",             "Linux": "spotify"},
    "vscode":             {"Windows": "code",                   "Darwin": "Visual Studio Code",  "Linux": "code"},
    "visual studio code": {"Windows": "code",                   "Darwin": "Visual Studio Code",  "Linux": "code"},
    "discord":            {"Windows": "Discord",                "Darwin": "Discord",             "Linux": "discord"},
    "telegram":           {"Windows": "Telegram",               "Darwin": "Telegram",            "Linux": "telegram"},
    "instagram":          {"Windows": "Instagram",              "Darwin": "Instagram",           "Linux": "https://www.instagram.com/"},
    "tiktok":             {"Windows": "TikTok",                 "Darwin": "TikTok",              "Linux": "https://www.tiktok.com/"},
    "notepad":            {"Windows": "notepad.exe",            "Darwin": "TextEdit",            "Linux": "gedit"},
    "calculator":         {"Windows": "calc.exe",               "Darwin": "Calculator",          "Linux": "gnome-calculator"},
    "terminal":           {"Windows": "cmd.exe",                "Darwin": "Terminal",            "Linux": "gnome-terminal"},
    "cmd":                {"Windows": "cmd.exe",                "Darwin": "Terminal",            "Linux": "bash"},
    "explorer":           {"Windows": "explorer.exe",           "Darwin": "Finder",              "Linux": "nautilus"},
    "file explorer":      {"Windows": "explorer.exe",           "Darwin": "Finder",              "Linux": "nautilus"},
    "paint":              {"Windows": "mspaint.exe",            "Darwin": "Preview",             "Linux": "gimp"},
    "word":               {"Windows": "winword",                "Darwin": "Microsoft Word",      "Linux": "libreoffice --writer"},
    "excel":              {"Windows": "excel",                  "Darwin": "Microsoft Excel",     "Linux": "libreoffice --calc"},
    "powerpoint":         {"Windows": "powerpnt",               "Darwin": "Microsoft PowerPoint","Linux": "libreoffice --impress"},
    "vlc":                {"Windows": "vlc",                    "Darwin": "VLC",                 "Linux": "vlc"},
    "zoom":               {"Windows": "Zoom",                   "Darwin": "zoom.us",             "Linux": "zoom"},
    "slack":              {"Windows": "Slack",                  "Darwin": "Slack",               "Linux": "slack"},
    "steam":              {"Windows": "steam",                  "Darwin": "Steam",               "Linux": "steam"},
    "task manager":       {"Windows": "taskmgr.exe",            "Darwin": "Activity Monitor",    "Linux": "gnome-system-monitor"},
    "settings":           {"Windows": "ms-settings:",           "Darwin": "System Preferences",  "Linux": "gnome-control-center"},
    "powershell":         {"Windows": "powershell.exe",         "Darwin": "Terminal",            "Linux": "bash"},
    "edge":               {"Windows": "msedge",                 "Darwin": "Microsoft Edge",      "Linux": "microsoft-edge"},
    "brave":              {"Windows": "brave",                  "Darwin": "Brave Browser",       "Linux": "brave-browser"},
    "obsidian":           {"Windows": "Obsidian",               "Darwin": "Obsidian",            "Linux": "obsidian"},
    "notion":             {"Windows": "Notion",                 "Darwin": "Notion",              "Linux": "notion"},
    "blender":            {"Windows": "blender",                "Darwin": "Blender",             "Linux": "blender"},
    "capcut":             {"Windows": "CapCut",                 "Darwin": "CapCut",              "Linux": "capcut"},
    "postman":            {"Windows": "Postman",                "Darwin": "Postman",             "Linux": "postman"},
    "figma":              {"Windows": "Figma",                  "Darwin": "Figma",               "Linux": "figma"},
}


def _normalize(raw: str) -> str:
    system = platform.system()
    key    = raw.lower().strip()
    if key in _APP_ALIASES:
        return _APP_ALIASES[key].get(system, raw)
    for alias_key, os_map in _APP_ALIASES.items():
        if alias_key in key or key in alias_key:
            return os_map.get(system, raw)
    return raw


def _is_running(app_name: str) -> bool:
    if not _PSUTIL:
        return True
    app_lower = app_name.lower().replace(" ", "").replace(".exe", "")
    try:
        for proc in psutil.process_iter(["name"]):
            try:
                proc_name = proc.info["name"].lower().replace(" ", "").replace(".exe", "")
                if app_lower in proc_name or proc_name in app_lower:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"[OpenApp] ⚠️ Could not inspect running processes: {e}")
    return False


def _launch_windows(app_name: str) -> bool:
    try:
        import pyautogui
        pyautogui.PAUSE = 0.1
        pyautogui.press("win")
        time.sleep(0.6)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(3.0)
        return True
    except Exception as e:
        print(f"[open_app] ⚠️ Windows launch failed: {e}")
        return False

def _launch_macos(app_name: str) -> bool:
    for target in (app_name, f"{app_name}.app"):
        try:
            result = subprocess.run(["open", "-a", target], capture_output=True, timeout=8)
            if result.returncode == 0:
                time.sleep(1.0)
                return True
            print(
                f"[open_app] ⚠️ 'open -a {target}' exited {result.returncode}: "
                f"{result.stderr.decode(errors='replace').strip()[:200]}"
            )
        except Exception as e:
            print(f"[open_app] ⚠️ 'open -a {target}' failed: {e}")

    try:
        import pyautogui
        pyautogui.hotkey("command", "space")
        time.sleep(0.6)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(1.5)
        return True
    except Exception as e:
        print(f"[open_app] ⚠️ macOS Spotlight failed: {e}")
        return False



def _launch_linux(app_name: str) -> bool:
    if app_name.startswith(("http://", "https://")):
        try:
            import webbrowser
            webbrowser.open(app_name)
            time.sleep(1.0)
            return True
        except Exception as e:
            print(f"[open_app] ⚠️ webbrowser.open('{app_name}') failed: {e}")
            return False

    binary = (
        shutil.which(app_name) or
        shutil.which(app_name.lower()) or
        shutil.which(app_name.lower().replace(" ", "-"))
    )
    if binary:
        try:
            subprocess.Popen([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)
            return True
        except OSError as e:
            print(f"[open_app] ⚠️ Could not start '{binary}': {e}")

    desktop_name = app_name.lower().replace(" ", "-")
    for command in (["xdg-open", app_name], ["gtk-launch", desktop_name]):
        try:
            result = subprocess.run(command, capture_output=True, timeout=5)
            if result.returncode == 0:
                return True
            print(
                f"[open_app] ⚠️ '{' '.join(command)}' exited {result.returncode}: "
                f"{result.stderr.decode(errors='replace').strip()[:200]}"
            )
        except Exception as e:
            print(f"[open_app] ⚠️ '{' '.join(command)}' failed: {e}")

    return False


_OS_LAUNCHERS = {
    "Windows": _launch_windows,
    "Darwin":  _launch_macos,
    "Linux":   _launch_linux,
}

# Apps where we know how to search-and-open a specific chat/contact
# after the app itself has launched.
_CHAT_CAPABLE_APPS = ("whatsapp", "telegram")


def _open_specific_chat(app_key: str, chat_name: str) -> bool:
    """
    Searches for and opens a specific chat/contact inside a messaging app.
    Does NOT type or send any message — only opens the conversation.
    Works for both the desktop Electron app (Ctrl+F search shortcut) and
    the browser-based version (Linux default), since both expose a
    focusable search box that responds to Ctrl+F.
    """
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.08

        time.sleep(1.8)  # let the app/page finish loading

        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.4)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.write(chat_name, interval=0.04)
        time.sleep(0.9)
        pyautogui.press("enter")
        time.sleep(0.5)

        return True
    except Exception as e:
        print(f"[open_app] ⚠️ Could not open chat '{chat_name}' in {app_key}: {e}")
        return False


def open_app(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params    = parameters or {}
    app_name  = params.get("app_name", "").strip()
    chat_name = (params.get("chat_name") or "").strip()

    if not app_name:
        return "Please specify which application to open, sir."

    system   = platform.system()
    launcher = _OS_LAUNCHERS.get(system)

    if launcher is None:
        return f"Unsupported OS: {system}"

    normalized = _normalize(app_name)
    print(f"[open_app] 🚀 Launching: {app_name} → {normalized} ({system})")

    if player:
        player.write_log(f"[open_app] {app_name}")

    app_key = app_name.lower().strip()
    wants_chat = bool(chat_name) and any(k in app_key for k in _CHAT_CAPABLE_APPS)

    try:
        success = launcher(normalized)

        if not success and normalized != app_name:
            success = launcher(app_name)

        if not success:
            return (
                f"I tried to open {app_name}, sir, but couldn't confirm it launched. "
                f"It may still be loading or might not be installed."
            )

        if wants_chat:
            if player:
                player.write_log(f"[open_app] opening chat: {chat_name}")
            if _open_specific_chat(app_key, chat_name):
                return f"Opened {chat_name}'s chat in {app_name}, sir."
            return (
                f"Opened {app_name}, sir, but I couldn't confirm the chat with "
                f"{chat_name} opened. You may need to search for it manually."
            )

        return f"Opened {app_name} successfully, sir."

    except Exception as e:
        print(f"[open_app] ❌ {e}")
        return f"Failed to open {app_name}, sir: {e}"
