import os
from typing import Any

# ─── Paths ───────────────────────────────────────────────────────────
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CORE_DIR)
VIZ_TMP_DIR = os.path.join(BASE_DIR, '.viz_tmp')

INDEX_REL = 'assets/index.html'

# ─── Global State ───────────────────────────────────────────────────
# Note: These are populated at runtime in app.py
_http_port = 0

def get_http_port() -> int:
    global _http_port
    return _http_port

def set_http_port(port: int) -> None:
    global _http_port
    _http_port = port

# ─── Session Data Store ─────────────────────────────────────────────
# In-memory store for visualization data served via the REST API.
# Keys are session IDs (short hex strings), values are JSON-serializable dicts.
_data_store: dict[str, Any] = {}

def store_session_data(session_id: str, data: Any) -> None:
    """Store visualization data for a session, evicting old entries."""
    global _data_store
    # Keep at most 4 sessions to bound memory usage
    while len(_data_store) >= 4:
        oldest_key = next(iter(_data_store))
        del _data_store[oldest_key]
    _data_store[session_id] = data

def get_session_data(session_id: str) -> Any | None:
    """Retrieve stored visualization data for a session."""
    return _data_store.get(session_id)

def clear_session_data() -> None:
    """Clear all stored session data."""
    global _data_store
    _data_store.clear()
