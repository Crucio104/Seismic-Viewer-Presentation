import os
import shutil
import threading
import atexit
import webview
import pathlib

# ─── Core Imports ────────────────────────────────────────────────────
from core.config import BASE_DIR, VIZ_TMP_DIR, INDEX_REL, set_http_port
from core.bridge import Api

# ─── Local HTTP Server ──────────────────────────────────────────────
_http_server = None

def _start_http_server():
    global _http_server
    if _http_server: return # Already running
    
    import http.server
    import socketserver
    import functools
    
    class _QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args): pass

    os.makedirs(VIZ_TMP_DIR, exist_ok=True)
    handler = functools.partial(_QuietHandler, directory=BASE_DIR)
    _http_server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    
    port = _http_server.server_address[1]
    set_http_port(port)
    
    t = threading.Thread(target=_http_server.serve_forever, daemon=True)
    t.start()
    print(f"Local server: http://127.0.0.1:{port}")


def _stop_http_server():
    global _http_server
    if _http_server:
        try:
            _http_server.shutdown()
            _http_server.server_close()
        except Exception:
            pass
        _http_server = None


# ─── Cleanup ────────────────────────────────────────────────────────

def _cleanup():
    """Fast cleanup: stop server. Temp files will be handled at startup or by OS."""
    try:
        _stop_http_server()
    except Exception:
        pass

atexit.register(_cleanup)


# ─── Entry point ─────────────────────────────────────────────────────

def main():
    _win_holder = []

    def win_ref():
        return _win_holder[0]

    api = Api(win_ref)

    start_url = pathlib.Path(os.path.join(BASE_DIR, INDEX_REL)).as_uri()
    window = webview.create_window(
        'Seismic Viewer',
        url=start_url,
        js_api=api,
        width=1150,
        height=850,
        min_size=(1000, 750),
        background_color='#050510'
    )
    _win_holder.append(window)

    def on_closing():
        print("Window closing...")
        return True

    if window is not None:
        window.events.closing += on_closing

    print("Starting Seismic Viewer…")
    try:
        webview.start(_start_http_server, debug=False)
    except KeyboardInterrupt:
        pass
    
    print("Window closed. Freeing terminal...")
    try:
        _stop_http_server()
        if os.path.exists(VIZ_TMP_DIR):
            if os.name == 'nt':
                import subprocess
                subprocess.run(['cmd', '/c', f'del /f /q "{VIZ_TMP_DIR}\\*.html"'], capture_output=True)
            else:
                shutil.rmtree(VIZ_TMP_DIR)
    except Exception:
        pass

if __name__ == '__main__':
    main()
