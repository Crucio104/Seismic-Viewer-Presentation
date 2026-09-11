from pathlib import Path
from typing import Any
import threading
import gc

# ─── Paths ───────────────────────────────────────────────────────────
CORE_DIR = Path(__file__).parent.absolute()
BASE_DIR = CORE_DIR.parent

INDEX_REL = Path('assets/index.html')
TEMP_DIR = BASE_DIR / 'temp'
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
# Keys are session IDs (short hex strings), values are JSON-serializable dicts.
_data_store: dict[str, Any] = {}
_html_store: dict[str, str] = {}
_store_lock = threading.Lock()

def store_session_data(session_id: str, data: dict[str, Any]) -> None:
    """Store visualization data for a session, evicting old entries."""
    with _store_lock:
        # Keep at most 5 sessions to bound memory usage
        evicted = False
        while len(_data_store) >= 5:
            oldest_key = next(iter(_data_store))
            del _data_store[oldest_key]
            evicted = True
        _data_store[session_id] = data
        if evicted:
            gc.collect()

def get_session_data(session_id: str) -> dict[str, Any] | None:
    """Retrieve stored visualization data for a session."""
    with _store_lock:
        return _data_store.get(session_id)

def cleanup_temp_files() -> None:
    """Clean up temporary files created during online imports."""
    if TEMP_DIR.exists():
        try:
            for f in TEMP_DIR.glob("ingv_*.csv"):
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
    """Store generated HTML for a view, evicting old entries."""
    with _store_lock:
        # Keep at most 3 views to bound memory usage (each 3D view HTML is ~12MB)
        evicted = False
        while len(_html_store) >= 3:
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
