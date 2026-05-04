from pathlib import Path
import uuid
import threading
import webview
import logging
import numpy as np
import asyncio
from typing import Any, Callable
from core.config import (
    BASE_DIR, get_http_port, store_session_data, 
    clear_session_data, TEMP_DIR
)
from core.history import get_recent_files, save_recent_file, clear_history
from core.online_importer import fetch_ingv_data
import engine

logger = logging.getLogger(__name__)

class Api:
    """Python ↔ JS bridge exposed via pywebview."""

    def __init__(self, window_ref: Callable[[], webview.Window]):
        self._window: Callable[[], webview.Window] = window_ref
        self._csv_path: str | None = None
        self._data: dict[str, Any] | None = None
        self._csv_info: dict[str, Any] | None = None
        self._html_cache: dict[tuple[Any, ...], str] = {}  # (csv_path, view_style, ...) -> rel_path
        self._socket_manager: Any = None
        self._event_loop: Any = None

    def set_socket_manager(self, manager: Any, loop: Any = None) -> None:
        """Set the FastAPI WebSocket manager and the event loop for progress push."""
        self._socket_manager = manager
        self._event_loop = loop

    # ── Helpers ──────────────────────────────────────────────────────

    def _make_url(self, viz_id: str) -> str:
        """Build an HTTP URL for the dynamic visualization endpoint."""
        port = get_http_port()
        return f'http://127.0.0.1:{port}/viz/{viz_id}'

    def _make_data_url(self, session_id: str) -> str:
        """Build the REST API URL for fetching session data."""
        port = get_http_port()
        return f'http://127.0.0.1:{port}/api/data/{session_id}'

    def _push_progress(self, msg: str) -> None:
        """Send a progress message to the hub overlay via WebSocket or JS fallback."""
        # 1. Try WebSocket (Fast & Async)
        if self._socket_manager and self._event_loop:
            try:
                # Use the stored event loop from uvicorn to schedule the broadcast
                asyncio.run_coroutine_threadsafe(
                    self._socket_manager.broadcast({"type": "progress", "msg": msg}),
                    self._event_loop
                )
            except Exception:
                pass
        
        # 2. Fallback to pywebview evaluate_js
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
            return self._process_csv_load(path)

        except Exception as e:
            logger.error("Error in select_csv", exc_info=True)
            return {'error': str(e)}

    def download_online_data(self, params: dict[str, Any]) -> dict[str, Any]:
        """Fetch data from INGV, save to CSV, and load it."""
        try:
            self._push_progress("Connecting to INGV servers...")
            
            # Run in a separate thread to avoid blocking the UI
            csv_path = fetch_ingv_data(params)
            self._push_progress("Processing downloaded data...")
            return self._process_csv_load(csv_path)
            
        except Exception as e:
            logger.error(f"Online import failed: {e}", exc_info=True)
            return {'error': str(e)}

    def _process_csv_load(self, path: str) -> dict[str, Any]:
        """Centralized logic to load and process a CSV file."""
        try:
            # OPTIMIZATION: Skip if already loaded
            if self._csv_path == path and self._data is not None:
                logger.info(f"File {Path(path).name} already in memory, skipping reload.")
                return self._csv_info

            data = engine.load_csv(path)
            self._csv_path = path
            self._data = data
            self._csv_info = {
                'filename': Path(path).name,
                'event_count': data['summary']['event_count'],
                'date_range': data['summary']['date_range'],
            }
            self._html_cache.clear()
            save_recent_file(path)
            return self._csv_info
        except ValueError as e:
            return {'error': str(e)}
        except Exception as e:
            logger.error(f"Failed to load CSV: {path}", exc_info=True)
            return {'error': f'Failed to load CSV: {e}'}

    def get_history(self) -> list[dict[str, str]]:
        """Return a list of recent files with their names and paths."""
        paths = get_recent_files()
        return [{'name': Path(p).name, 'path': p} for p in paths]

    def load_recent_file(self, path: str) -> dict[str, Any] | None:
        """Load a file directly from path without dialog."""
        if not Path(path).exists():
            return {'error': 'File no longer exists.'}
        return self._process_csv_load(path)

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

            # Generate a unique session ID for the data endpoint
            session_id = uuid.uuid4().hex[:12]
            data_url = self._make_data_url(session_id)

            logger.info(f"Generating view {view_style}…")
            res = engine.build_view_html(
                self._data, view_style,
                on_progress=self._push_progress,
                anim_mode=anim_mode, 
                window_days=window_days,
                clustering_method=clustering_method,
                clustering_params=clustering_params,
                data_url=data_url,
                session_id=session_id,
            )
            html, is_fallback = res

            viz_id = uuid.uuid4().hex[:8]
            from core.config import store_viz_html
            store_viz_html(viz_id, html)

            if not is_fallback:
                # Keep cache bounded to 10 entries
                if len(self._html_cache) >= 10:
                    oldest_key = next(iter(self._html_cache))
                    del self._html_cache[oldest_key]
                self._html_cache[cache_key] = viz_id

            self._push_progress("Opening visualization…")
            self._window().load_url(self._make_url(viz_id))
            logger.info(f"View {view_style} loaded via API.")
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

            # 1. Clustering Subset: Filter ONLY by Date (using fast precalculated cumulative indices)
            start_idx = 0
            end_idx = len(d['longitude'])
            
            if t1 or t2:
                dates_unique = d['visual_pack']['unique_dates']
                date_to_cum = d['visual_pack']['date_to_cum']
                
                if t1:
                    # Find first date >= t1
                    for i, dt in enumerate(dates_unique):
                        if dt >= t1:
                            if i > 0:
                                start_idx = date_to_cum[dates_unique[i-1]]
                            break
                    else:
                        start_idx = end_idx # No dates match
                        
                if t2:
                    # Find first date > t2 to define the upper bound
                    for i, dt in enumerate(dates_unique):
                        if dt > t2:
                            if i > 0:
                                end_idx = date_to_cum[dates_unique[i-1]]
                            else:
                                end_idx = 0
                            break

            if start_idx >= end_idx: 
                return {'error': 'No data in this date range'}

            # 2. Visualization Mask: Vectorized filtering for Mag/Dep
            mags = np.array(d['magnitude'][start_idx:end_idx])
            deps = np.abs(d['depth'][start_idx:end_idx])
            viz_mask = (mags >= m1) & (mags <= m2) & (deps >= d1) & (deps <= d2)

            updated_traces = engine.get_cluster_update_traces(
                longitude=d['longitude'][start_idx:end_idx],
                latitude=d['latitude'][start_idx:end_idx],
                magnitude=mags.tolist(),  # Already sliced
                depth=d['depth'][start_idx:end_idx],
                hover=d['visual_pack']['hover'][start_idx:end_idx],
                clustering_method=method,
                clustering_params=params,
                viz_mask=viz_mask
            )
            return updated_traces

        except Exception as e:
            logger.error("Bridge error", exc_info=True)
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
            logger.error("Bridge error", exc_info=True)
            return {'error': str(e)}

    def get_animated_clustering(self, method: str, params: dict[str, Any], step_frames: int) -> dict[str, Any]:
        """Precalculate clustering and planes for the animation timeline."""
        if self._data is None: return {'error': 'No data'}
        try:
            cluster_mapping = engine.get_animation_clustering(
                self._data, 
                method=method, 
                params=params, 
                step_frames=int(step_frames)
            )
            return cluster_mapping
        except Exception as e:
            logger.error("Bridge error", exc_info=True)
            return {'error': str(e)}



    def change_file(self) -> bool:
        """Go back to the file picker screen."""
        self._csv_path = None
        self._data = None
        self._csv_info = None
        self._html_cache.clear()
        return True

    def clear_map_cache(self) -> bool | str:
        """Delete and recreate the map cache directory, delete temp files, and clear in-memory caches."""
        from core.geo_utils import MAP_CACHE_DIR, build_map_mesh
        import shutil
        try:
            # 1. Clear Map Cache
            if MAP_CACHE_DIR.exists():
                shutil.rmtree(MAP_CACHE_DIR)
            MAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            
            # 2. Clear Online Import Temp Files
            if TEMP_DIR.exists():
                shutil.rmtree(TEMP_DIR)
            
            # 3. CRITICAL: Clear both the HTML path cache and the memory mesh cache
            self._html_cache.clear()
            build_map_mesh.cache_clear()
            
            # Also clear the recent files history and session data
            clear_history()
            clear_session_data()
            
            return True
        except Exception as e:
            logger.error("Error in clear_map_cache", exc_info=True)
            return str(e)
