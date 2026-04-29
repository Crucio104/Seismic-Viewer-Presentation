import json
from pathlib import Path
from core.config import HISTORY_FILE

def get_recent_files() -> list[str]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            paths = json.load(f)
            # Filter only existing files
            return [p for p in paths if Path(p).exists()]
    except Exception:
        return []

def save_recent_file(path: str) -> None:
    recent = get_recent_files()
    # Remove if already exists to move it to top
    if path in recent:
        recent.remove(path)
    recent.insert(0, path)
    # Keep only last 4
    recent = recent[:4]
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(recent, f)
    except Exception:
        pass

def clear_history() -> None:
    try:
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
    except Exception:
        pass
