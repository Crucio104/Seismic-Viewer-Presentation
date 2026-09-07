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
        temp_file = HISTORY_FILE.with_suffix('.tmp')
        with open(temp_file, "w", encoding='utf-8') as f:
            json.dump(recent, f, indent=2)
        temp_file.replace(HISTORY_FILE)
    except Exception:
        pass

def clear_history() -> None:
    try:
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
    except Exception:
        pass
