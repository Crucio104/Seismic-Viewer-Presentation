from pathlib import Path
import uuid
import threading
import webview
import logging
import numpy as np
import asyncio
import time
from typing import Any, Callable

from core.config import (
    BASE_DIR, get_http_port, 
    clear_session_data, TEMP_DIR, store_viz_html,
    MAP_CACHE_DIR
)
from core.history import get_recent_files, save_recent_file, clear_history
from core.online_importer import fetch_ingv_data
from core.geo_utils import build_map_mesh
import engine

logger = logging.getLogger(__name__)

class Api:
    """Python ↔ JS bridge exposed via pywebview."""

    def __init__(self, window_ref: Callable[[], webview.Window]):
        self._window: Callable[[], webview.Window] = window_ref
        self._csv_path: str | None = None
        self._data: dict[str, Any] | None = None
        self._csv_info: dict[str, Any] | None = None
        self._html_cache: dict[tuple, str] = {} 
        self._socket_manager: Any = None
        self._event_loop: Any = None

    def set_socket_manager(self, manager: Any, loop: Any = None) -> None:
        """Set the FastAPI WebSocket manager and the event loop."""
        self._socket_manager = manager
        self._event_loop = loop

    # --- Internal Helpers ---

    def _make_url(self, viz_id: str) -> str:
        return f'http://127.0.0.1:{get_http_port()}/viz/{viz_id}'

    def _make_data_url(self, session_id: str) -> str:
        return f'http://127.0.0.1:{get_http_port()}/api/data/{session_id}'

    def _push_progress(self, msg: str) -> None:
        """Send a progress message to the UI."""
        if self._socket_manager and self._event_loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._socket_manager.broadcast({"type": "progress", "msg": msg}),
                    self._event_loop
                )
            except Exception:
                pass
        
        try:
            safe_msg = msg.replace('\\', '\\\\').replace("'", "\\'")
            self._window().evaluate_js(f"if(typeof updateProgress==='function') updateProgress('{safe_msg}')")
        except Exception:
            pass

    def _inject_dark_overlay(self):
        """Prevent white flash during navigation."""
        try:
            self._window().evaluate_js(
                "document.body.style.cssText='background:#050510 !important;';"
                "var _ov=document.createElement('div');"
                "_ov.style.cssText='position:fixed;inset:0;z-index:9999999;background:#050510;';"
                "document.body.appendChild(_ov);"
            )
            time.sleep(0.05)
        except Exception:
            pass

    # --- File Operations ---

    def select_csv(self) -> dict[str, Any] | None:
        """Open native file dialog to select a CSV."""
        try:
            result = self._window().create_file_dialog(
                webview.FileDialog.OPEN,
                directory=str(BASE_DIR),
                allow_multiple=False,
                file_types=('CSV Files (*.csv)',),
            )
            if not result:
                return None
            path = result[0] if isinstance(result, (list, tuple)) else result
            return self._process_csv_load(path)
        except Exception as e:
            logger.error("Error in select_csv", exc_info=True)
            return {'error': str(e)}

    def download_online_data(self, params: dict[str, Any]) -> dict[str, Any]:
        """Fetch data from INGV servers."""
        try:
            self._push_progress("Connecting to INGV servers...")
            csv_path = fetch_ingv_data(params)
            self._push_progress("Processing downloaded data...")
            return self._process_csv_load(csv_path)
        except Exception as e:
            logger.error(f"Online import failed: {e}", exc_info=True)
            return {'error': str(e)}

    def _process_csv_load(self, path: str) -> dict[str, Any]:
        """Centralized CSV loading logic."""
        try:
            if self._csv_path == path and self._data is not None:
                return self._csv_info

            data = engine.load_csv(path)
            self._csv_path, self._data = path, data
            self._csv_info = {
                'filename': Path(path).name,
                'event_count': data['summary']['event_count'],
                'date_range': data['summary']['date_range'],
            }
            self._html_cache.clear()
            save_recent_file(path)
            return self._csv_info
        except Exception as e:
            logger.error(f"Failed to load CSV: {path}", exc_info=True)
            return {'error': str(e)}

    def get_csv_info(self) -> dict[str, Any] | None:
        """Return information about the currently loaded CSV."""
        return self._csv_info

    def get_history(self) -> list[dict[str, str]]:
        return [{'name': Path(p).name, 'path': p} for p in get_recent_files()]

    def load_recent_file(self, path: str) -> dict[str, Any] | None:
        if not Path(path).exists():
            return {'error': 'File no longer exists.'}
        return self._process_csv_load(path)

    # --- Visualization Navigation ---

    def load_view(self, view_style: int, anim_mode: str = 'accumulation', window_days: int = 5, clustering_method: str = 'kmeans', clustering_params: dict[str, Any] | None = None) -> None:
        """Background thread for view generation."""
        if self._data is None:
            return {'error': 'No CSV loaded.'}
        
        kwargs = {
            'anim_mode': anim_mode,
            'window_days': window_days,
            'clustering_method': clustering_method,
            'clustering_params': clustering_params
        }
        threading.Thread(target=self._generate_and_navigate, args=(view_style,), kwargs=kwargs, daemon=True).start()

    def _generate_and_navigate(self, view_style: int, **kwargs) -> None:
        """Generate HTML and navigate the window."""
        try:
            # 1. Check Cache
            c_params = kwargs.get('clustering_params')
            c_params_frozen = frozenset(c_params.items()) if c_params else None
            cache_key = (self._csv_path, view_style, kwargs.get('anim_mode'), kwargs.get('window_days'), kwargs.get('clustering_method'), c_params_frozen)

            if cache_key in self._html_cache:
                self._push_progress("Loading from cache…")
                self._inject_dark_overlay()
                self._window().load_url(self._make_url(self._html_cache[cache_key]))
                return

            # 2. Generate New View
            session_id = uuid.uuid4().hex[:12]
            res = engine.build_view_html(
                self._data, view_style,
                on_progress=self._push_progress,
                data_url=self._make_data_url(session_id),
                session_id=session_id,
                **kwargs
            )
            html, is_fallback = res
            viz_id = uuid.uuid4().hex[:8]
            store_viz_html(viz_id, html)

            if not is_fallback:
                if len(self._html_cache) >= 10:
                    self._html_cache.pop(next(iter(self._html_cache)))
                self._html_cache[cache_key] = viz_id

            # 3. Navigate
            self._push_progress("Opening visualization…")
            self._inject_dark_overlay()
            self._window().load_url(self._make_url(viz_id))
            
        except Exception as e:
            logger.error(f"Failed to generate view {view_style}", exc_info=True)
            self._push_progress(f"Error: {e}")

    # --- Async API Updates ---

    def get_cluster_update(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """WebSocket endpoint for clustering updates."""
        if not self._data:
            return {'error': 'No data'}
        try:
            d = self._data
            t1, t2 = params.get('start_date', ""), params.get('end_date', "")
            
            # Fast index slicing
            start_idx, end_idx = 0, len(d['longitude'])
            if t1 or t2:
                dates = d['visual_pack']['unique_dates']
                cum = d['visual_pack']['date_to_cum']
                if t1:
                    for i, dt in enumerate(dates):
                        if dt >= t1:
                            if i > 0:
                                start_idx = cum[dates[i-1]]
                            break
                    else:
                        start_idx = end_idx
                if t2:
                    for i, dt in enumerate(dates):
                        if dt > t2:
                            end_idx = cum[dates[i-1]] if i > 0 else 0
                            break

            if start_idx >= end_idx:
                return {'error': 'Empty date range'}

            mags, deps = np.array(d['magnitude'][start_idx:end_idx]), np.abs(d['depth'][start_idx:end_idx])
            viz_mask = (mags >= float(params.get('mag_min', 0))) & (mags <= float(params.get('mag_max', 10))) & \
                       (deps >= float(params.get('dep_min', 0))) & (deps <= float(params.get('dep_max', 10000)))

            return engine.get_cluster_update_traces(
                longitude=d['longitude'][start_idx:end_idx],
                latitude=d['latitude'][start_idx:end_idx],
                magnitude=mags.tolist(),
                depth=d['depth'][start_idx:end_idx],
                hover=d['visual_pack']['hover'][start_idx:end_idx],
                clustering_method=method, clustering_params=params, viz_mask=viz_mask,
                origin_lat=d.get('origin_lat'), origin_lon=d.get('origin_lon')
            )
        except Exception as e:
            logger.error("Cluster update failed", exc_info=True)
            return {'error': str(e)}

    def get_structural_planes(self, radius_km: float = 2.0, min_pts: int = 10, window_days: int = 5) -> dict[str, Any]:
        if not self._data:
            return {'error': 'No data'}
        return engine.get_animation_planes(self._data, radius_km=radius_km, min_pts=min_pts, window_days=window_days)

    def get_animated_clustering(self, method: str = 'kmeans', params: dict[str, Any] | None = None, plane_step: int = 5) -> dict[str, Any]:
        if not self._data:
            return {'error': 'No data'}
        return engine.get_animation_clustering(self._data, method=method, params=params, plane_step=plane_step)

    def change_file(self) -> bool:
        self._csv_path = self._data = self._csv_info = None
        self._html_cache.clear()
        return True

    def clear_map_cache(self) -> bool | str:
        import shutil
        try:
            if MAP_CACHE_DIR.exists():
                shutil.rmtree(MAP_CACHE_DIR)
            if TEMP_DIR.exists():
                shutil.rmtree(TEMP_DIR)
            MAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            
            self._html_cache.clear()
            build_map_mesh.cache_clear()
            clear_history()
            clear_session_data()
            return True
        except Exception as e:
            return str(e)
