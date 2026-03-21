#Run with:  python app.py

import os
import atexit
import threading
import traceback
import http.server
import functools
import socketserver
import shutil
import uuid

import webview

import engine  # our visualization library

# ─── Paths ───────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
VIZ_TMP_DIR = os.path.join(BASE_DIR, '.viz_tmp')

# Relative paths (from BASE_DIR) used for HTTP URLs
FILE_PICKER_REL = 'assets/file_picker.html'
HUB_REL = 'assets/hub.html'


# ─── Local HTTP Server ──────────────────────────────────────────────
# Serves files over HTTP so that browser tile requests (OSM, etc.)
# carry a proper Referer header — avoids 403 errors from file:// URIs.

class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler that suppresses console access logs."""
    def log_message(self, format, *args):
        pass


_http_server = None
_http_port = 0


def _start_http_server():
    global _http_server, _http_port
    os.makedirs(VIZ_TMP_DIR, exist_ok=True)
    handler = functools.partial(_QuietHandler, directory=BASE_DIR)
    _http_server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    _http_port = _http_server.server_address[1]
    t = threading.Thread(target=_http_server.serve_forever, daemon=True)
    t.start()
    print(f"Local server: http://127.0.0.1:{_http_port}")


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
    """Robust cleanup: stop server and remove temp files."""
    print("Cleaning up resources...")
    try:
        _stop_http_server()
        if os.path.exists(VIZ_TMP_DIR):
            # shutil.rmtree can fail if files are locked by the browser
            # so we ignore errors but try our best
            shutil.rmtree(VIZ_TMP_DIR, ignore_errors=True)
    except Exception as e:
        print(f"Cleanup warning: {e}")


atexit.register(_cleanup)


# ─── API exposed to JavaScript ──────────────────────────────────────

class Api:
    """Python ↔ JS bridge exposed via pywebview."""

    def __init__(self, window_ref):
        self._window = window_ref
        self._csv_path = None
        self._data = None
        self._csv_info = None
        self._html_cache = {}  # (csv_path, view_style) -> rel_path

    # ── Helpers ──────────────────────────────────────────────────────

    def _make_url(self, rel_path):
        """Build an HTTP URL from a path relative to BASE_DIR."""
        return f'http://127.0.0.1:{_http_port}/{rel_path.replace(os.sep, "/")}'

    def _navigate_delayed(self, rel_path, delay=0.15):
        """Schedule a page navigation after a short delay.

        Allows pywebview to return the JS callback result
        before the current page is destroyed.
        """
        url = self._make_url(rel_path)
        threading.Timer(delay, self._window().load_url, args=(url,)).start()

    def _push_progress(self, msg):
        """Send a progress message to the hub overlay via JS."""
        try:
            safe_msg = msg.replace('\\', '\\\\').replace("'", "\\'")
            self._window().evaluate_js(
                f"if(typeof updateProgress==='function')"
                f"updateProgress('{safe_msg}')"
            )
        except Exception:
            pass

    # ── File selection ───────────────────────────────────────────────

    def select_csv(self):
        """Open native file dialog, validate the CSV, return summary or error."""
        try:
            result = self._window().create_file_dialog(
                webview.FileDialog.OPEN,
                directory=BASE_DIR,
                allow_multiple=False,
                file_types=('CSV Files (*.csv)',),
            )
            if not result:
                return None  # user cancelled

            path = result[0] if isinstance(result, (list, tuple)) else result

            # Validate & parse
            data = engine.load_csv(path)
            self._csv_path = path
            self._data = data
            self._csv_info = {
                'filename': os.path.basename(path),
                'event_count': data['summary']['event_count'],
                'date_range': data['summary']['date_range'],
            }
            self._html_cache.clear()  # new CSV → invalidate cache
            return self._csv_info

        except ValueError as e:
            return {'error': str(e)}
        except Exception as e:
            traceback.print_exc()
            return {'error': f'Unexpected error: {e}'}

    # ── Navigation ───────────────────────────────────────────────────

    def navigate_hub(self):
        """Navigate the window to the hub screen."""
        self._navigate_delayed(HUB_REL)

    def get_csv_info(self):
        """Return current CSV info for the hub badge."""
        return self._csv_info

    def load_view(self, view_style):
        """Start visualization generation in a background thread."""
        if self._data is None:
            return {'error': 'No CSV file loaded.'}

        threading.Thread(
            target=self._generate_and_navigate,
            args=(view_style,),
            daemon=True,
        ).start()

    def _generate_and_navigate(self, view_style):
        """Background worker: generate HTML (or use cache), then navigate."""
        try:
            cache_key = (self._csv_path, view_style)

            # Check cache
            if cache_key in self._html_cache:
                self._push_progress("Loading from cache…")
                rel_path = self._html_cache[cache_key]
                self._window().load_url(self._make_url(rel_path))
                return

            print(f"Generating view {view_style}…")
            html = engine.build_view_html(
                self._data, view_style,
                on_progress=self._push_progress,
            )

            # Write to temp file
            fname = f'view_{uuid.uuid4().hex[:8]}.html'
            fpath = os.path.join(VIZ_TMP_DIR, fname)
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(html)

            rel_path = os.path.relpath(fpath, BASE_DIR)
            self._html_cache[cache_key] = rel_path

            self._push_progress("Opening visualization…")
            self._window().load_url(self._make_url(rel_path))
            print(f"View {view_style} loaded.")
        except Exception as e:
            traceback.print_exc()
            self._push_progress(f"Error: {e}")

    def go_back(self):
        """Return to the hub screen."""
        self._navigate_delayed(HUB_REL)

    def change_file(self):
        """Go back to the file picker screen."""
        self._csv_path = None
        self._data = None
        self._csv_info = None
        self._html_cache.clear()
        self._navigate_delayed(FILE_PICKER_REL)


# ─── Entry point ─────────────────────────────────────────────────────

def main():
    _start_http_server()

    _win_holder = []

    def win_ref():
        return _win_holder[0]

    api = Api(win_ref)

    start_url = f'http://127.0.0.1:{_http_port}/{FILE_PICKER_REL}'
    window = webview.create_window(
        'Seismic Viewer',
        url=start_url,
        js_api=api,
        width=1100,
        height=750,
        min_size=(800, 500),
    )
    _win_holder.append(window)

    def on_closing():
        print("Window closing...")
        return True

    window.events.closing += on_closing

    print("Starting Seismic Viewer…")
    try:
        webview.start(debug=False)
    except KeyboardInterrupt:
        pass  # Expected when closing the window with the 'X' button in Windows
    
    # Perform cleanup explicitly because os._exit(0) bypasses atexit handlers
    _cleanup()
    print("Application closed correctly.")
    os._exit(0)



if __name__ == '__main__':
    main()
