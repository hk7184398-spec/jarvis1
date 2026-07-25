import os
from datetime import datetime
from pathlib import Path


def restrict_permissions(path: Path) -> None:
    """Make a file readable by its owner only (no-op on Windows)."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def atomic_write_text(path: Path, text: str) -> None:
    """Write via a temp file so a failed write cannot truncate the original."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def quarantine_corrupt_file(path: Path, label: str = "") -> Path | None:
    """Move an unreadable file aside so it is not silently overwritten."""
    backup = path.with_suffix(f".corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
    prefix = f"[{label}] " if label else ""
    try:
        path.replace(backup)
        print(f"{prefix}🗄️ Unreadable file moved to: {backup}")
        return backup
    except OSError as e:
        print(f"{prefix}❌ Could not preserve unreadable file {path}: {e}")
        return None
