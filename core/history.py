import os
import json
from pathlib import Path

HISTORY_FILE = Path.home() / ".seismic_viewer_history.json"

def get_recent_files():
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            paths = json.load(f)
            # Filter only existing files
            return [p for p in paths if os.path.exists(p)]
    except Exception:
        return []

def save_recent_file(path):
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

def clear_history():
    try:
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
    except Exception:
        pass
