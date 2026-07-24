import os
import subprocess
from pathlib import Path

from core.config import is_linux, is_mac, is_windows


def get_desktop_dir() -> Path:
    """User's desktop directory, honouring XDG_DESKTOP_DIR on Linux."""
    xdg = os.environ.get("XDG_DESKTOP_DIR", "")
    if xdg and Path(xdg).exists():
        return Path(xdg)
    return Path.home() / "Desktop"


def open_url(url: str) -> None:
    try:
        if is_mac():
            subprocess.Popen(["open", url])
        elif is_linux():
            subprocess.Popen(["xdg-open", url])
        else:
            subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
    except Exception as e:
        print(f"[Platform] ⚠️ Could not open URL: {e}")


def open_in_text_editor(path: str | Path) -> None:
    try:
        if is_windows():
            subprocess.Popen(["notepad.exe", str(path)])
        elif is_mac():
            subprocess.Popen(["open", "-t", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        print(f"[Platform] ⚠️ Could not open text editor: {e}")


def save_to_desktop(filename: str, content: str, open_editor: bool = False) -> Path:
    desktop = get_desktop_dir()
    desktop.mkdir(parents=True, exist_ok=True)
    filepath = desktop / filename
    filepath.write_text(content, encoding="utf-8")
    if open_editor:
        open_in_text_editor(filepath)
    return filepath


def run_first_available(commands: list[list[str]]) -> bool:
    """Run the first command whose executable exists on PATH. Returns True if one ran."""
    for cmd in commands:
        try:
            if subprocess.run(["which", cmd[0]], capture_output=True).returncode == 0:
                subprocess.Popen(cmd)
                return True
        except Exception:
            continue
    return False
