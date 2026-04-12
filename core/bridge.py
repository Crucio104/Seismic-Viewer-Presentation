import os
import uuid
import threading
import traceback
import webview
import engine
from core.config import BASE_DIR, VIZ_TMP_DIR, INDEX_REL, get_http_port

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
        port = get_http_port()
        return f'http://127.0.0.1:{port}/{rel_path.replace(os.sep, "/")}'

    def _navigate_delayed(self, rel_path, delay=0.15):
        """Schedule a page navigation after a short delay."""
        url = self._make_url(rel_path)
        threading.Timer(delay, self._window().load_url, args=(url,)).start()

    def _push_progress(self, msg):
        """Send a progress message to the hub overlay via JS."""
        try:
            safe_msg = msg.replace('\\', '\\\\').replace("'", "\\'")
            self._window().evaluate_js(
                f"if(typeof updateProgress==='function') updateProgress('{safe_msg}')"
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
        self._window().evaluate_js("showHub()")

    def get_csv_info(self):
        """Return current CSV info for the hub badge."""
        return self._csv_info

    def load_view(self, view_style, anim_mode='accumulation', window_days=5, clustering_method='kmeans', clustering_params=None):
        """Start visualization generation in a background thread."""
        if self._data is None:
            return {'error': 'No CSV file loaded.'}

        threading.Thread(
            target=self._generate_and_navigate,
            args=(view_style, anim_mode, window_days, clustering_method, clustering_params),
            daemon=True,
        ).start()

    def _generate_and_navigate(self, view_style, anim_mode, window_days, clustering_method='kmeans', clustering_params=None):
        """Background worker: generate HTML (or use cache), then navigate."""
        try:
            c_params_frozen = frozenset(clustering_params.items()) if clustering_params else None
            cache_key = (self._csv_path, view_style, anim_mode, window_days, clustering_method, c_params_frozen)

            if cache_key in self._html_cache:
                self._push_progress("Loading from cache…")
                rel_path = self._html_cache[cache_key]
                self._window().load_url(self._make_url(rel_path))
                return

            print(f"Generating view {view_style}…")
            res = engine.build_view_html(
                self._data, view_style,
                on_progress=self._push_progress,
                anim_mode=anim_mode, 
                window_days=window_days,
                clustering_method=clustering_method,
                clustering_params=clustering_params
            )
            html, is_fallback = res

            fname = f'view_{uuid.uuid4().hex[:8]}.html'
            fpath = os.path.join(VIZ_TMP_DIR, fname)
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(html)

            rel_path = os.path.relpath(fpath, BASE_DIR)
            if not is_fallback:
                self._html_cache[cache_key] = rel_path

            self._push_progress("Opening visualization…")
            self._window().load_url(self._make_url(rel_path))
            print(f"View {view_style} loaded.")
        except Exception as e:
            traceback.print_exc()
            self._push_progress(f"Error: {e}")

    def go_back(self):
        """Return to the hub screen."""
        self._navigate_delayed(INDEX_REL)

    def change_file(self):
        """Go back to the file picker screen."""
        self._csv_path = None
        self._data = None
        self._csv_info = None
        self._html_cache.clear()
        return True

    def clear_map_cache(self):
        """Delete and recreate the map cache directory."""
        from core.geo_utils import MAP_CACHE_DIR
        import shutil
        try:
            if os.path.exists(MAP_CACHE_DIR):
                shutil.rmtree(MAP_CACHE_DIR)
            os.makedirs(MAP_CACHE_DIR, exist_ok=True)
            self._html_cache.clear()
            return True
        except Exception as e:
            traceback.print_exc()
            return str(e)
