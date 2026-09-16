from pathlib import Path
from typing import Any
import threading
import gc

# ─── Paths ───────────────────────────────────────────────────────────
CORE_DIR = Path(__file__).parent.absolute()
BASE_DIR = CORE_DIR.parent

INDEX_REL = Path('assets/index.html')
TEMP_DIR = BASE_DIR / 'temp'
DROPPED_FILES_DIR = BASE_DIR / 'cache' / 'dropped_files'
HISTORY_FILE = Path.home() / ".seismic_viewer_history.json"

# ─── CSV Schema ──────────────────────────────────────────────────────
# Standardized mapping for seismic data columns
CSV_SCHEMA = {
    'time': ['time', 'date', 'datetime', 'utc', 'time_utc', 'origintime'],
    'lat': ['lat', 'latitude'],
    'lon': ['lon', 'longitude'],
    'depth': ['depth', 'depth_km'],
    'mag': ['mag', 'magnitude', 'md', 'ml', 'mw']
}
# Canonical header for exported files
CSV_CANONICAL_HEADER = ["#EventID", "Time", "Latitude", "Longitude", "Depth", "MD", "MD Error", "Area", "Type", "Level"]
MIN_MAGNITUDE = -10.0
MISSING_MAG_VALUE = 0.1
MISSING_DEPTH_VALUE = 0.0

# ─── Geography ──────────────────────────────────────────────────────
KM_PER_DEGREE = 111.32
SECONDS_PER_DAY = 86400

# ─── Online Import (INGV GOSSIP) ───────────────────────────────────
GOSSIP_BASE_URL = "https://terremoti.ov.ingv.it/gossip"
DEFAULT_LOCATED_ONLY = True
DEFAULT_EXCLUDE_MISSING = True

ANIMATION_BASE_DURATION_MS = 1000

# ─── Mapping & Resolution ──────────────────────────────────────────
MESH_HD_SIZE = 1024
PALETTE_COLORS = 256
MAP_CACHE_DIR = BASE_DIR / 'resources' / '.map_cache'
INGV_CACHE_DIR = BASE_DIR / 'resources' / '.ingv_cache'

# ─── Global State ───────────────────────────────────────────────────
# Note: These are populated at runtime in app.py
_http_port = 0

def get_http_port() -> int:
    return _http_port

def set_http_port(port: int) -> None:
    global _http_port
    _http_port = port


# ─── Session Data Store ─────────────────────────────────────────────
# In-memory store for visualization data served via the REST API.
# Keys are session IDs (short hex strings), values are (timestamp, data) tuples.
import time as _time

_data_store: dict[str, tuple[float, dict[str, Any]]] = {}
_html_store: dict[str, str] = {}
_store_lock = threading.Lock()

_SESSION_MAX_COUNT = 5
_SESSION_TTL_SECONDS = 600  # Evict sessions older than 10 minutes

def store_session_data(session_id: str, data: dict[str, Any]) -> None:
    """Store visualization data for a session, evicting old or expired entries."""
    now = _time.monotonic()
    with _store_lock:
        # Evict expired sessions first
        expired = [k for k, (ts, _) in _data_store.items() if now - ts > _SESSION_TTL_SECONDS]
        for k in expired:
            del _data_store[k]
        # Then enforce count limit
        evicted = False
        while len(_data_store) >= _SESSION_MAX_COUNT:
            oldest_key = next(iter(_data_store))
            del _data_store[oldest_key]
            evicted = True
        _data_store[session_id] = (now, data)
        if evicted or expired:
            gc.collect()

def get_session_data(session_id: str) -> dict[str, Any] | None:
    """Retrieve stored visualization data for a session."""
    with _store_lock:
        entry = _data_store.get(session_id)
        return entry[1] if entry is not None else None

MAX_TEMP_FILES = 4

def cleanup_temp_files(max_keep: int = 0) -> None:
    """
    Clean up temporary files created during imports and visualization exports.
    If max_keep > 0, keeps only the `max_keep` most recently modified files, deleting older ones.
    If max_keep == 0, deletes all temporary files in TEMP_DIR.
    """
    if TEMP_DIR.exists():
        try:
            temp_files = sorted(
                [f for f in TEMP_DIR.iterdir() if f.is_file() and not f.name.startswith('.')],
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            to_delete = temp_files[max_keep:] if max_keep > 0 else temp_files
            for f in to_delete:
                try:
                    f.unlink()
                except Exception:
                    pass
        except Exception:
            pass

def enforce_temp_dir_limit(max_keep: int = MAX_TEMP_FILES) -> None:
    """Ensure the temp directory holds at most max_keep recent files."""
    cleanup_temp_files(max_keep=max_keep)

def cleanup_dropped_files(max_keep: int = MAX_TEMP_FILES) -> None:
    """
    Keep at most `max_keep` most recently modified dropped files in cache/dropped_files/.
    If max_keep == 0, deletes all dropped cache files.
    """
    if DROPPED_FILES_DIR.exists():
        try:
            files = sorted(
                [f for f in DROPPED_FILES_DIR.iterdir() if f.is_file()],
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            to_delete = files[max_keep:] if max_keep > 0 else files
            for f in to_delete:
                try:
                    f.unlink()
                except Exception:
                    pass
        except Exception:
            pass

def clear_session_data() -> None:
    """Clear all stored session data and free memory."""
    with _store_lock:
        _data_store.clear()
        _html_store.clear()
    gc.collect()

# ─── HTML View Store ───────────────────────────────────────────────

def store_viz_html(viz_id: str, html: str) -> None:
    """Store generated HTML for the active view, immediately evicting old entries."""
    with _store_lock:
        # Keep at most 1 active view to strictly bound memory usage (~12MB per view)
        evicted = False
        while len(_html_store) >= 1:
            oldest_key = next(iter(_html_store))
            del _html_store[oldest_key]
            evicted = True
        _html_store[viz_id] = html
        if evicted:
            gc.collect()

def get_viz_html(viz_id: str) -> str | None:
    """Retrieve stored HTML for a view."""
    with _store_lock:
        return _html_store.get(viz_id)
