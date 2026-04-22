import os
import uuid
import threading
import traceback
import webview
import logging
import numpy as np
from typing import Any, Callable

logger = logging.getLogger(__name__)
import engine
from core.config import BASE_DIR, VIZ_TMP_DIR, get_http_port
from core.history import get_recent_files, save_recent_file, clear_history

class Api:
    """Python ↔ JS bridge exposed via pywebview."""

    def __init__(self, window_ref: Callable[[], webview.Window]):
        self._window: Callable[[], webview.Window] = window_ref
        self._csv_path: str | None = None
        self._data: dict[str, Any] | None = None
        self._csv_info: dict[str, Any] | None = None
        self._html_cache: dict[tuple[Any, ...], str] = {}  # (csv_path, view_style, ...) -> rel_path

    # ── Helpers ──────────────────────────────────────────────────────

    def _make_url(self, rel_path: str) -> str:
        """Build an HTTP URL from a path relative to BASE_DIR."""
        port = get_http_port()
        return f'http://127.0.0.1:{port}/{rel_path.replace(os.sep, "/")}'



    def _push_progress(self, msg: str) -> None:
        """Send a progress message to the hub overlay via JS."""
        try:
            safe_msg = msg.replace('\\', '\\\\').replace("'", "\\'")
            self._window().evaluate_js(
                f"if(typeof updateProgress==='function') updateProgress('{safe_msg}')"
            )
        except Exception:
            pass

    # ── File selection ───────────────────────────────────────────────

    def select_csv(self) -> dict[str, Any] | None:
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
            save_recent_file(path)
            return self._csv_info

        except ValueError as e:
            return {'error': str(e)}
        except Exception as e:
            logger.error("Unexpected error in select_csv", exc_info=True)
            return {'error': f'Unexpected error: {e}'}

    def get_history(self) -> list[dict[str, str]]:
        """Return a list of recent files with their names and paths."""
        paths = get_recent_files()
        return [{'name': os.path.basename(p), 'path': p} for p in paths]

    def load_recent_file(self, path: str) -> dict[str, Any] | None:
        """Load a file directly from path without dialog."""
        try:
            if not os.path.exists(path):
                return {'error': 'File no longer exists.'}
            
            data = engine.load_csv(path)
            self._csv_path = path
            self._data = data
            self._csv_info = {
                'filename': os.path.basename(path),
                'event_count': data['summary']['event_count'],
                'date_range': data['summary']['date_range'],
            }
            self._html_cache.clear()
            save_recent_file(path)
            return self._csv_info
        except Exception as e:
            return {'error': str(e)}

    # ── Navigation ───────────────────────────────────────────────────


    def get_csv_info(self) -> dict[str, Any] | None:
        """Return current CSV info for the hub badge."""
        return self._csv_info

    def load_view(self, view_style: int, anim_mode: str = 'accumulation', window_days: int = 5, clustering_method: str = 'kmeans', clustering_params: dict[str, Any] | None = None) -> None:
        """Start visualization generation in a background thread."""
        if self._data is None:
            return {'error': 'No CSV file loaded.'}

        threading.Thread(
            target=self._generate_and_navigate,
            args=(view_style, anim_mode, window_days, clustering_method, clustering_params),
            daemon=True,
        ).start()

    def _generate_and_navigate(self, view_style: int, anim_mode: str, window_days: int, clustering_method: str = 'kmeans', clustering_params: dict[str, Any] | None = None) -> None:
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
            logger.info(f"View {view_style} loaded.")
        except Exception as e:
            logger.error(f"Failed to generate view {view_style}", exc_info=True)
            self._push_progress(f"Error: {e}")

    def get_cluster_update(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Asynchronously recalculate clusters for the existing view."""
        if self._data is None: return {'error': 'No data'}
        try:
            d = self._data
            # Extract filters from params
            m1 = float(params.get('mag_min', 0))
            m2 = float(params.get('mag_max', 10))
            d1 = float(params.get('dep_min', 0))
            d2 = float(params.get('dep_max', 10000))
            t1 = params.get('start_date', "")
            t2 = params.get('end_date', "")

            # 1. Clustering Subset: Filter ONLY by Date 
            # (Clustering definition should be stable regardless of mag/dep)
            cluster_idx = []
            for i in range(len(d['longitude'])):
                dt = d['times'][i][:10]
                if (not t1 or dt >= t1) and (not t2 or dt <= t2):
                    cluster_idx.append(i)

            if not cluster_idx: return {'error': 'No data in this date range'}

            # 2. Visualization Mask: Of those in the Date Range, which satisfy Mag/Dep?
            viz_mask = []
            for i in cluster_idx:
                m = d['magnitude'][i]
                dp = abs(d['depth'][i])
                viz_mask.append(m >= m1 and m <= m2 and dp >= d1 and dp <= d2)

            updated_traces = engine.get_cluster_update_traces(
                longitude=[d['longitude'][i] for i in cluster_idx],
                latitude=[d['latitude'][i] for i in cluster_idx],
                magnitude=[d['magnitude'][i] for i in cluster_idx],
                depth=[d['depth'][i] for i in cluster_idx],
                hover=[d['visual_pack']['hover'][i] for i in cluster_idx],
                clustering_method=method,
                clustering_params=params,
                viz_mask=np.array(viz_mask)
            )
            return updated_traces

        except Exception as e:
            traceback.print_exc()
            return {'error': str(e)}


    def get_structural_planes(self, radius_km: float, min_pts: int, window_days: int) -> dict[str, Any]:
        """Recalculate structural planes for the entire animation timeline."""
        if self._data is None: return {'error': 'No data'}
        try:
            planes_mapping = engine.get_animation_planes(
                self._data, 
                radius_km=float(radius_km), 
                min_pts=int(min_pts), 
                window_days=int(window_days)
            )
            return planes_mapping
        except Exception as e:
            traceback.print_exc()
            return {'error': str(e)}


    def change_file(self) -> bool:
        """Go back to the file picker screen."""
        self._csv_path = None
        self._data = None
        self._csv_info = None
        self._html_cache.clear()
        return True

    def clear_map_cache(self) -> bool | str:
        """Delete and recreate the map cache directory and clear in-memory caches."""
        from core.geo_utils import MAP_CACHE_DIR, build_map_mesh
        import shutil
        try:
            if os.path.exists(MAP_CACHE_DIR):
                shutil.rmtree(MAP_CACHE_DIR)
            os.makedirs(MAP_CACHE_DIR, exist_ok=True)
            
            # CRITICAL: Clear both the HTML path cache and the memory mesh cache
            self._html_cache.clear()
            build_map_mesh.cache_clear()
            
            # Also clear the recent files history
            clear_history()
            
            return True
        except Exception as e:
            traceback.print_exc()
            return str(e)

