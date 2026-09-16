import json
import logging
from pathlib import Path
from core.config import HISTORY_FILE

logger = logging.getLogger(__name__)

# In-memory cache to avoid re-reading disk and re-validating file existence on every call
_recent_cache: list[str] | None = None

def get_recent_files() -> list[str]:
    """Return recent files, reading from disk only on first call or after cache invalidation."""
    global _recent_cache
    if _recent_cache is not None:
        return list(_recent_cache)

    if not HISTORY_FILE.exists():
        _recent_cache = []
        return []
    try:
        with open(HISTORY_FILE, encoding='utf-8') as f:
            paths = json.load(f)
            # Filter only existing files
            _recent_cache = [p for p in paths if Path(p).exists()]
            return list(_recent_cache)
    except Exception as e:
        logger.warning(f"Failed to load recent files: {e}")
        _recent_cache = []
        return []

def save_recent_file(path: str) -> None:
    """Add a file to the recent list (in-memory + disk), moving it to the top if already present."""
    global _recent_cache
    recent = get_recent_files()
    # Remove if already exists to move it to top
    if path in recent:
        recent.remove(path)
    recent.insert(0, path)
    # Keep only last 4
    recent = recent[:4]
    _recent_cache = list(recent)
    try:
        temp_file = HISTORY_FILE.with_suffix('.tmp')
        with open(temp_file, "w", encoding='utf-8') as f:
            json.dump(recent, f, indent=2)
        temp_file.replace(HISTORY_FILE)
    except Exception as e:
        logger.warning(f"Failed to save recent files: {e}")

def clear_history() -> None:
    """Clear all recent files from disk and in-memory cache."""
    global _recent_cache
    _recent_cache = []
    try:
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
    except Exception as e:
        logger.warning(f"Failed to clear history: {e}")
