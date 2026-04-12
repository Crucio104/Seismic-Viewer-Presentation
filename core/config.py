import os

# ─── Paths ───────────────────────────────────────────────────────────
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CORE_DIR)
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
VIZ_TMP_DIR = os.path.join(BASE_DIR, '.viz_tmp')

INDEX_REL = 'assets/index.html'

# ─── Global State ───────────────────────────────────────────────────
# Note: These are populated at runtime in app.py
_http_port = 0

def get_http_port():
    global _http_port
    return _http_port

def set_http_port(port):
    global _http_port
    _http_port = port
