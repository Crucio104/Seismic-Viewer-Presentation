from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any
import asyncio
import base64
import bisect
import gc
import logging
import shutil
import threading
import time
import uuid

import numpy as np
import webview

from core.config import (
    BASE_DIR, get_http_port, 
    clear_session_data, store_viz_html,
    MAP_CACHE_DIR, INGV_CACHE_DIR, get_session_data, cleanup_temp_files,
    DROPPED_FILES_DIR, cleanup_dropped_files
)
from core.history import get_recent_files, save_recent_file, clear_history as clear_history_file
from core.online_importer import fetch_ingv_dataframe
from core.geo_utils import build_map_mesh
from core.layer_utils import process_tomography_data, process_uplift_data, process_stations_data
from core.exporter import (
    write_single_cluster_csv,
    write_single_cluster_geojson,
    write_single_cluster_json,
    write_clusters_zip,
    collect_cluster_export_items
)
from core.loader import load_csv, process_seismic_dataframe
from core import engine

logger = logging.getLogger(__name__)

class Api:
    """Python ↔ JS bridge exposed via pywebview."""

    def __init__(self, window_ref: Callable[[], webview.Window]):
        self._window: Callable[[], webview.Window] = window_ref
        self._csv_path: str | None = None
        self._data: dict[str, Any] | None = None
        self._csv_info: dict[str, Any] | None = None
        self._stored_layer_paths: dict[str, dict[str, str] | None] = {'stations': None, 'uplift': None, 'tomography': None}
        self._history_stack: list[dict[str, Any]] = []
        self._history_idx: int = -1
        self._socket_manager: object | None = None
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._last_cluster_result: dict[str, Any] | None = None
        self._nav_lock = threading.Lock()
        self._nav_generation: int = 0

    def set_socket_manager(self, manager: object, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Set the FastAPI WebSocket manager and the event loop."""
        self._socket_manager = manager
        self._event_loop = loop

    # --- Internal Helpers ---

    def _make_url(self, viz_id: str) -> str:
        return f'http://127.0.0.1:{get_http_port()}/viz/{viz_id}'

    def _make_data_url(self, session_id: str) -> str:
        return f'http://127.0.0.1:{get_http_port()}/api/data/{session_id}'

    def _navigate_frame(self, url: str) -> None:
        """Navigate the visualization frame without reloading the top-level application shell."""
        try:
            safe_url = url.replace('\\', '\\\\').replace("'", "\\'")
            js_code = (
                f"if(window.SeismicApp && typeof window.SeismicApp.navigateTo === 'function') {{"
                f"    window.SeismicApp.navigateTo('{safe_url}');"
                f"}} else {{"
                f"    window.location.href = '{safe_url}';"
                f"}}"
            )
            self._window().evaluate_js(js_code)
        except Exception as e:
            logger.warning(f"Error navigating frame: {e}, falling back to window.load_url")
            try:
                self._inject_dark_overlay()
                self._window().load_url(url)
            except Exception as le:
                logger.debug(f"Failed to load url directly: {le}")

    def clear_history(self) -> dict:
        """Clear all history sessions and caches."""
        self._history_stack.clear()
        self._history_idx = -1
        logger.info("History and clustering sessions cleared.")
        return {'status': 'success'}

    def _push_progress(self, msg: str) -> None:
        """Send a progress message to the UI."""
        if self._socket_manager and self._event_loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._socket_manager.broadcast({"type": "progress", "msg": msg}),
                    self._event_loop
                )
            except Exception as e:
                logger.debug(f"Failed to broadcast progress via WS: {e}")
        
        try:
            safe_msg = msg.replace('\\', '\\\\').replace("'", "\\'")
            self._window().evaluate_js(f"if(typeof updateProgress==='function') updateProgress('{safe_msg}')")
        except Exception as e:
            logger.debug(f"Failed to push progress via evaluate_js: {e}")

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
        except Exception as e:
            logger.debug(f"Failed to inject dark overlay: {e}")

    # --- File Operations ---

    def select_csv(self) -> dict[str, Any] | None:
        """Open native file dialog to select a dataset (CSV, GeoJSON, JSON)."""
        try:
            result = self._window().create_file_dialog(
                webview.FileDialog.OPEN,
                directory=str(BASE_DIR),
                allow_multiple=False,
                file_types=(
                    'Supported Datasets (*.csv;*.geojson;*.json)',
                    'CSV Files (*.csv)',
                    'GeoJSON Files (*.geojson)',
                    'JSON Files (*.json)',
                    'All Files (*.*)'
                ),
            )
            if not result:
                return None
            path = result[0] if isinstance(result, (list, tuple)) else result
            return self._process_csv_load(path)
        except Exception as e:
            logger.error("Error in select_csv", exc_info=True)
            return {'error': str(e)}

    def save_screenshot(self, base64_data: str, filename: str = 'seismic_viewer_export.png') -> dict[str, Any]:
        """Open native save dialog and write the base64 image data to a file."""
        try:
            # Open save file dialog
            result = self._window().create_file_dialog(
                webview.FileDialog.SAVE,
                directory=str(Path.home()),
                save_filename=filename,
                file_types=('PNG Image (*.png)',),
            )
            
            if not result:
                return {'status': 'cancelled'}
            
            save_path = result[0] if isinstance(result, (list, tuple)) else result
            
            # Decode base64 data
            _, encoded = base64_data.split(",", 1) if "," in base64_data else ("", base64_data)
            data = base64.b64decode(encoded)
            
            # Write to file
            with open(save_path, 'wb') as f:
                f.write(data)
                
            return {'status': 'success', 'path': save_path}
        except Exception as e:
            logger.error("Error in save_screenshot", exc_info=True)
            return {'error': str(e)}

    def save_current_csv(self) -> dict[str, Any]:
        """Open native save dialog and save a copy of the currently loaded dataset in its original format."""
        try:
            if not self._csv_path or not Path(self._csv_path).exists():
                return {'error': 'No dataset loaded or file not found.'}

            original_path = Path(self._csv_path)
            original_filename = original_path.name
            suffix = original_path.suffix.lower()

            if suffix == '.geojson':
                file_types = ('GeoJSON Files (*.geojson)', 'All Files (*.*)')
            elif suffix == '.json':
                file_types = ('JSON Files (*.json)', 'All Files (*.*)')
            else:
                suffix = '.csv'
                if not original_filename.lower().endswith('.csv'):
                    original_filename += '.csv'
                file_types = ('CSV Files (*.csv)', 'All Files (*.*)')

            result = self._window().create_file_dialog(
                webview.FileDialog.SAVE,
                directory=str(Path.home()),
                save_filename=original_filename,
                file_types=file_types,
            )

            if not result:
                return {'status': 'cancelled'}

            save_path = result[0] if isinstance(result, (list, tuple)) else result
            save_path = str(save_path)
            if not save_path.lower().endswith(suffix):
                save_path += suffix

            shutil.copy2(self._csv_path, save_path)
            logger.info(f"Dataset successfully saved to: {save_path}")
            save_recent_file(save_path)
            return {'status': 'success', 'path': save_path}
        except Exception as e:
            logger.error("Error in save_current_csv", exc_info=True)
            return {'error': str(e)}

    def download_online_data(self, params: dict[str, Any]) -> dict[str, Any]:
        """Fetch data from INGV servers directly in memory."""
        try:
            self._push_progress("Connecting to INGV servers...")
            df, csv_path = fetch_ingv_dataframe(params, on_progress=self._push_progress)
            self._push_progress("Packaging downloaded data...")
            data = process_seismic_dataframe(df)
            self._csv_path, self._data = csv_path, data
            self._stored_layer_paths = {'stations': None, 'uplift': None, 'tomography': None}
            self._csv_info = {
                'filename': Path(csv_path).name,
                'event_count': data['summary']['event_count'],
                'date_range': data['summary']['date_range'],
                'total_days': data['summary'].get('total_days', 365),
                'swarms_count': data['summary'].get('swarms_count', 0),
            }
            save_recent_file(csv_path)
            return self._csv_info
        except Exception as e:
            logger.error(f"Online import failed: {e}", exc_info=True)
            return {'error': str(e)}

    def _process_csv_load(self, path: str) -> dict[str, Any]:
        """Centralized CSV loading logic."""
        try:
            if self._csv_path == path and self._data is not None:
                return self._csv_info

            if self._csv_path is not None and self._csv_path != path:
                self._stored_layer_paths = {'stations': None, 'uplift': None, 'tomography': None}

            data = load_csv(path)
            self._csv_path, self._data = path, data
            self._csv_info = {
                'filename': Path(path).name,
                'event_count': data['summary']['event_count'],
                'date_range': data['summary']['date_range'],
                'total_days': data['summary'].get('total_days', 365),
                'swarms_count': data['summary'].get('swarms_count', 0),
            }
            save_recent_file(path)
            return self._csv_info
        except Exception as e:
            logger.error(f"Failed to load CSV: {path}", exc_info=True)
            return {'error': str(e)}

    def load_csv_content(self, filename: str, content: str) -> dict[str, Any]:
        """Load a CSV directly from file text content (used for Drag & Drop)."""
        try:
            DROPPED_FILES_DIR.mkdir(parents=True, exist_ok=True)
            safe_name = Path(filename).name
            lower_name = safe_name.lower()
            if not (lower_name.endswith('.csv') or lower_name.endswith('.geojson') or lower_name.endswith('.json')):
                safe_name += '.csv'
            target_path = DROPPED_FILES_DIR / safe_name
            target_path.write_text(content, encoding='utf-8')
            cleanup_dropped_files(max_keep=4)
            return self._process_csv_load(str(target_path))
        except Exception as e:
            logger.error(f"Failed to load dropped CSV: {filename}", exc_info=True)
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

    def clear_recent_history(self) -> dict[str, Any]:
        """Clear recent files history and delete unsaved temporary INGV CSV downloads."""
        try:
            clear_history_file()
            cleanup_temp_files()
            cleanup_dropped_files(max_keep=0)
            logger.info("Recent history and temporary INGV CSV files cleared.")
            return {'status': 'success'}
        except Exception as e:
            logger.error("Error clearing recent history", exc_info=True)
            return {'error': str(e)}

    # --- Visualization Navigation ---

    def load_view(self, view_style: int, anim_mode: str = 'accumulation', window_days: int = 30, step_days: int = 7, clustering_method: str = 'dbscan', clustering_params: dict[str, Any] | None = None) -> None:
        """Background thread for view generation."""
        if self._data is None:
            return {'error': 'No CSV loaded.'}
        
        if clustering_params is None:
            clustering_params = {}
            
        kwargs = {
            'anim_mode': anim_mode,
            'window_days': window_days,
            'step_days': step_days,
            'clustering_method': clustering_method,
            'clustering_params': clustering_params
        }
        with self._nav_lock:
            self._history_stack.clear()
            self._history_stack.append({'view_style': view_style, 'kwargs': kwargs})
            self._history_idx = 0
            self._nav_generation += 1
            gen = self._nav_generation
        threading.Thread(target=self._generate_and_navigate, args=(view_style,), kwargs=dict(nav_gen=gen, **kwargs), daemon=True).start()

    def load_subcluster_view(self, indices: list[int], context_indices: list[int] | None = None, clustering_method: str = 'dbscan', clustering_params: dict[str, Any] | None = None, locked_clusters: dict[str, list[int]] | None = None) -> None:
        """Background thread for sub-cluster view generation."""
        if self._data is None:
            return
        
        if clustering_params is None:
            clustering_params = {}
            
        locked_map = None
        if locked_clusters:
            locked_map = {int(k): list(v) for k, v in locked_clusters.items()}

        kwargs = {
            'clustering_method': clustering_method,
            'clustering_params': clustering_params,
            'target_indices': indices,
            'context_indices': context_indices,
            'locked_clusters': locked_map
        }
        with self._nav_lock:
            # Truncate future history if we diverge
            if self._history_idx >= 0:
                self._history_stack = self._history_stack[:self._history_idx + 1]
            
            self._history_stack.append({'view_style': 4, 'kwargs': kwargs})
            self._history_idx = len(self._history_stack) - 1
            self._nav_generation += 1
            gen = self._nav_generation
        threading.Thread(target=self._generate_and_navigate, args=(4,), kwargs=dict(nav_gen=gen, **kwargs), daemon=True).start()

    def go_back(self) -> None:
        with self._nav_lock:
            if self._history_idx > 0:
                self._history_idx -= 1
                prev = self._history_stack[self._history_idx]
                self._nav_generation += 1
                gen = self._nav_generation
                threading.Thread(target=self._generate_and_navigate, args=(prev['view_style'],), kwargs=dict(nav_gen=gen, **prev['kwargs']), daemon=True).start()
            else:
                try:
                    self._window().evaluate_js(
                        "if(window.SeismicApp && typeof window.SeismicApp.showHub==='function') "
                        "window.SeismicApp.showHub(); "
                        "else if(typeof transitionToHub==='function') transitionToHub();"
                    )
                except Exception:
                    pass

    def go_forward(self) -> None:
        with self._nav_lock:
            if self._history_idx < len(self._history_stack) - 1:
                self._history_idx += 1
                nxt = self._history_stack[self._history_idx]
                self._nav_generation += 1
                gen = self._nav_generation
                threading.Thread(target=self._generate_and_navigate, args=(nxt['view_style'],), kwargs=dict(nav_gen=gen, **nxt['kwargs']), daemon=True).start()

    def get_history_status(self) -> dict[str, bool]:
        return {
            'can_go_back': self._history_idx > 0,
            'can_go_forward': self._history_idx < len(self._history_stack) - 1
        }

    def update_history_state(self, clustering_method: str, clustering_params: dict, locked_clusters: dict | None) -> None:
        if 0 <= self._history_idx < len(self._history_stack):
            curr = self._history_stack[self._history_idx]
            curr['kwargs']['clustering_method'] = clustering_method
            curr['kwargs']['clustering_params'] = clustering_params
            if locked_clusters:
                curr['kwargs']['locked_clusters'] = {int(k): list(v) for k, v in locked_clusters.items()}
            else:
                curr['kwargs']['locked_clusters'] = None

    def apply_subclusters(self, new_sub_labels: list[int]) -> dict[str, Any]:
        if not self._data:
            return {'error': 'No data'}
        try:
            if self._history_idx < 1:
                return {'error': 'No previous view to apply to'}
            
            curr_view = self._history_stack[self._history_idx]
            prev_view = self._history_stack[self._history_idx - 1]
            
            method = prev_view['kwargs'].get('clustering_method', 'dbscan')
            params = prev_view['kwargs'].get('clustering_params', {})
            
            if params and 'custom_labels' in params:
                global_labels = np.array(params['custom_labels'])
            else:
                res = engine.get_cluster_update_traces(
                    self._data['longitude'], self._data['latitude'], self._data['magnitude'],
                    self._data['depth'], np.array(self._data['visual_pack']['hover']),
                    method, params,
                    viz_mask=None,
                    origin_lat=self._data.get('origin_lat', 0),
                    origin_lon=self._data.get('origin_lon', 0)
                )
                global_labels = np.array(res['labels'])
                
            new_sub_labels = np.array(new_sub_labels, dtype=int)
            max_global = int(np.max(global_labels)) if len(global_labels) > 0 else -1
            target_indices = curr_view['kwargs'].get('target_indices', [])
            
            u_before, c_before = np.unique(global_labels, return_counts=True)
            logger.info(f"apply_subclusters: BEFORE global_labels = {u_before} with counts = {c_before}")
            
            logger.info(f"apply_subclusters: len(new_sub_labels)={len(new_sub_labels)}, len(target_indices)={len(target_indices)}, max_global={max_global}")
            
            # Identify the original label in custom_labels to clean up orphans
            if len(target_indices) > 0 and len(global_labels) > 0:
                original_labels = global_labels[target_indices]
                valid_originals = original_labels[original_labels >= 0]
                if len(valid_originals) > 0:
                    # Find the most common original label (should be uniform, but use most common to be safe)
                    most_common = Counter(valid_originals).most_common(1)[0][0]
                    # Set any points with this original label that are NOT in target_indices to noise (-1)
                    orphan_mask = (global_labels == most_common)
                    orphan_mask[target_indices] = False
                    global_labels[orphan_mask] = -1

            for local_idx, global_idx in enumerate(target_indices):
                if local_idx < len(new_sub_labels):
                    sub_l = new_sub_labels[local_idx]
                    if sub_l >= 0:
                        global_labels[global_idx] = max_global + 1 + sub_l
                    else:
                        global_labels[global_idx] = -1
                    
            unique_lbls, counts = np.unique(global_labels, return_counts=True)
            logger.info(f"apply_subclusters: unique global_labels now = {unique_lbls} with counts = {counts}")
            
            self._history_stack.pop()
            
            if 'clustering_params' not in prev_view['kwargs'] or prev_view['kwargs']['clustering_params'] is None:
                prev_view['kwargs']['clustering_params'] = {}
            prev_view['kwargs']['clustering_params']['custom_labels'] = global_labels.tolist()
            
            threading.Thread(target=self._generate_and_navigate, args=(prev_view['view_style'],), kwargs=prev_view['kwargs'], daemon=True).start()
            return {'status': 'success'}
        except Exception as e:
            logger.error("Apply subclusters failed", exc_info=True)
            return {'error': str(e)}

    def _generate_and_navigate(self, view_style: int, nav_gen: int = 0, **kwargs) -> None:
        """Generate HTML and navigate the window."""
        try:
            if nav_gen != 0 and nav_gen != self._nav_generation:
                return

            # 1. Check History Cache
            curr_history = None
            if hasattr(self, '_history_idx') and 0 <= self._history_idx < len(self._history_stack):
                curr_history = self._history_stack[self._history_idx]

            if curr_history and 'viz_id' in curr_history:
                self._push_progress("Loading session from memory…")
                # Clear last_cluster_result so export relies on JS payload
                self._last_cluster_result = None

                url = self._make_url(curr_history['viz_id']) + f"?t={int(time.time()*1000)}"
                if view_style == 4:
                    url += "&subcluster=true"
                if nav_gen != 0 and nav_gen != self._nav_generation:
                    return
                self._navigate_frame(url)
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

            if not is_fallback and curr_history is not None:
                curr_history['viz_id'] = viz_id

            if view_style in (3, 4):
                s_data = get_session_data(session_id)
                if s_data and ('cluster_indices' in s_data or 'cluster' in s_data):
                    self._last_cluster_result = {
                        'method': s_data.get('clustering_method', 'dbscan'),
                        'params': s_data.get('clustering_params', {}),
                        'labels': s_data.get('cluster'),
                        'cluster_indices': s_data.get('cluster_indices')
                    }

            # 3. Navigate
            self._push_progress("Opening visualization…")
            url = self._make_url(viz_id)
            if view_style == 4:
                url += "?subcluster=true"
            self._navigate_frame(url)
            
        except Exception as e:
            logger.exception(f"Failed to generate view {view_style}")
            self._push_progress(f"Error: {e}")

    # --- Async API Updates ---

    def get_cluster_update(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """WebSocket endpoint for clustering updates."""
        if not self._data:
            return {'error': 'No data'}
        try:
            d = self._data
            t1 = params.get('start_date', "").strip() if params.get('start_date') else ""
            t2 = params.get('end_date', "").strip() if params.get('end_date') else ""
            
            # Fast index slicing using binary search
            start_idx, end_idx = 0, len(d['longitude'])
            if t1 or t2:
                dates = d['visual_pack']['unique_dates']
                cum = d['visual_pack']['date_to_cum']
                if t1:
                    i = bisect.bisect_left(dates, t1)
                    if i < len(dates):
                        start_idx = cum[dates[i - 1]] if i > 0 else 0
                    else:
                        start_idx = end_idx
                if t2:
                    j = bisect.bisect_right(dates, t2)
                    if j < len(dates):
                        end_idx = cum[dates[j - 1]] if j > 0 else 0
                    else:
                        end_idx = len(d['longitude'])

            if start_idx >= end_idx:
                return {'error': 'No events found in selected date range'}

            mags, deps = np.array(d['magnitude'][start_idx:end_idx]), np.abs(d['depth'][start_idx:end_idx])
            viz_mask = (mags >= float(params.get('mag_min', 0))) & (mags <= float(params.get('mag_max', 10))) & \
                       (deps >= float(params.get('dep_min', 0))) & (deps <= float(params.get('dep_max', 10000)))

            target_mask = None
            if 'subcluster_target_indices' in params:
                target_mask = np.zeros(len(d['longitude']), dtype=bool)
                target_mask[params['subcluster_target_indices']] = True
                target_mask = target_mask[start_idx:end_idx]

            context_mask = None
            if 'subcluster_context_indices' in params and params['subcluster_context_indices'] is not None:
                context_mask = np.zeros(len(d['longitude']), dtype=bool)
                context_mask[params['subcluster_context_indices']] = True
                context_mask = context_mask[start_idx:end_idx]

            actual_mask = viz_mask
            if target_mask is not None:
                actual_mask = viz_mask & target_mask

            global_indices = np.where(actual_mask)[0] + start_idx

            dnums = np.array(d.get('dates_num', d.get('dnum', [])))
            f_dnums = dnums[start_idx:end_idx] if len(dnums) >= end_idx else None

            res = engine.get_cluster_update_traces(
                longitude=d['longitude'][start_idx:end_idx],
                latitude=d['latitude'][start_idx:end_idx],
                magnitude=mags.tolist(),
                depth=d['depth'][start_idx:end_idx],
                hover=d['visual_pack']['hover'][start_idx:end_idx],
                clustering_method=method, clustering_params=params, viz_mask=viz_mask,
                origin_lat=d.get('origin_lat'), origin_lon=d.get('origin_lon'),
                subcluster_target_mask=target_mask,
                subcluster_context_mask=context_mask,
                global_indices=global_indices,
                dates_num=f_dnums
            )

            # Map the returned labels back to global indices
            labels = np.array(res['labels'])
            
            cluster_indices = defaultdict(list)
            # labels length should match global_indices length
            if len(labels) == len(global_indices):
                for lbl, g_idx in zip(labels, global_indices):
                    cluster_indices[int(lbl)].append(int(g_idx))
            
            res['cluster_indices'] = dict(cluster_indices)
            res['method'] = method
            res['params'] = params if params is not None else {}
            self._last_cluster_result = {
                'method': method,
                'params': params if params is not None else {},
                'labels': res.get('labels'),
                'cluster_indices': cluster_indices
            }
            return res
        except Exception as e:
            logger.error("Cluster update failed", exc_info=True)
            return {'error': str(e)}

    def auto_tune_time_window(self) -> dict[str, Any]:
        """Auto-tune spatio-temporal correlation time window based on current catalog."""
        if not self._data:
            return {'time_window_hours': 72.0, 'time_window_days': 3.0}
        dnums = self._data.get('dates_num', self._data.get('dnum'))
        if dnums is not None and len(dnums) > 0:
            dummy = {}
            val_hours = engine.auto_tune_time_window(dnums, dummy)
            return {'time_window_hours': val_hours, 'time_window_days': dummy.get('time_window_days', round(val_hours / 24.0, 2))}
        return {'time_window_hours': 72.0, 'time_window_days': 3.0}

    def get_structural_planes(self, radius_km: float = 2.0, min_pts: int = 10, window_days: int = 30, anim_mode: str = 'accumulation', step_days: int = 7) -> dict[str, Any]:
        if not self._data:
            return {'error': 'No data'}
        return engine.get_animation_planes(self._data, radius_km=radius_km, min_pts=min_pts, window_days=window_days, anim_mode=anim_mode, step_days=step_days)

    def get_animated_clustering(self, method: str = 'dbscan', params: dict[str, Any] | None = None, plane_step: int = 5) -> dict[str, Any]:
        if not self._data:
            return {'error': 'No data'}
        res = engine.get_animation_clustering(self._data, method=method, params=params, plane_step=plane_step)
        self._last_cluster_result = {
            'method': method,
            'params': params if params is not None else {},
            'labels': res.get('global_labels'),
            'cluster_indices': None
        }
        return res

    def change_file(self) -> bool:
        self._csv_path = self._data = self._csv_info = None
        self._stored_layer_paths = {'stations': None, 'uplift': None, 'tomography': None}
        clear_session_data()
        gc.collect()
        return True

    def clear_map_cache(self) -> bool | str:
        try:
            if MAP_CACHE_DIR.exists():
                shutil.rmtree(MAP_CACHE_DIR)
            MAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)

            if INGV_CACHE_DIR.exists():
                shutil.rmtree(INGV_CACHE_DIR)
            INGV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            
            build_map_mesh.cache_clear()
            clear_session_data()
            gc.collect()
            return True
        except Exception as e:
            return str(e)

    def select_layer_file(self, layer_type: str) -> dict[str, Any] | None:
        """Open native file dialog to select map image, uplift CSV, tomography CSV, or station CSV."""
        try:
            file_types = ('CSV Files (*.csv)',) if layer_type in ('uplift', 'tomography', 'stations') else ('Image Files (*.jpg;*.png;*.jpeg)',)
            result = self._window().create_file_dialog(
                webview.FileDialog.OPEN,
                directory=str(BASE_DIR),
                allow_multiple=False,
                file_types=file_types,
            )
            if not result:
                return None
            path = result[0] if isinstance(result, (list, tuple)) else result
            res = {'status': 'success', 'path': str(path), 'filename': Path(path).name, 'type': layer_type}
            if layer_type in self._stored_layer_paths:
                self._stored_layer_paths[layer_type] = {'path': str(path), 'filename': Path(path).name}
            return res
        except Exception as e:
            logger.error(f"Error in select_layer_file for {layer_type}", exc_info=True)
            return {'error': str(e)}

    def get_stored_layer_paths(self) -> dict[str, Any]:
        """Return currently saved layer CSV paths for the current dataset session."""
        return self._stored_layer_paths

    def apply_external_layers(self, params: dict[str, Any]) -> dict[str, Any]:
        """Process and return data for selected layers (uplift, tomography, stations)."""
        res = {'status': 'success', 'layers': {}}
        try:
            target_date = params.get('target_date')
            if not target_date and self._data and 'times' in self._data:
                times = self._data.get('times', [])
                if times:
                    target_date = str(times[-1])[:10]
                    
            stations_path = params.get('stations_path') or (self._stored_layer_paths.get('stations', {}) or {}).get('path')
            uplift_path = params.get('uplift_path') or (self._stored_layer_paths.get('uplift', {}) or {}).get('path')
            tomo_path = params.get('tomography_path') or (self._stored_layer_paths.get('tomography', {}) or {}).get('path')

            if stations_path:
                self._stored_layer_paths['stations'] = {'path': str(stations_path), 'filename': Path(stations_path).name}
            if uplift_path:
                self._stored_layer_paths['uplift'] = {'path': str(uplift_path), 'filename': Path(uplift_path).name}
            if tomo_path:
                self._stored_layer_paths['tomography'] = {'path': str(tomo_path), 'filename': Path(tomo_path).name}

            if uplift_path:
                uplift_res = process_uplift_data(uplift_path, target_date_str=target_date, stations_path=stations_path)
                res['layers']['uplift'] = uplift_res
                
            if tomo_path:
                tomo_res = process_tomography_data(tomo_path)
                res['layers']['tomography'] = tomo_res
                
            if stations_path:
                stations_res = process_stations_data(stations_path)
                res['layers']['stations'] = stations_res
                
            return res
        except Exception as e:
            logger.error("Error in apply_external_layers", exc_info=True)
            return {'status': 'error', 'error': str(e), 'message': str(e)}

    def export_single_cluster_csv(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Export a single selected cluster as a CSV or GeoJSON file via native Save dialog."""
        try:
            if not self._data:
                return {'status': 'error', 'message': 'No dataset loaded'}

            payload = payload or {}
            fmt = str(payload.get('format', 'csv')).lower().strip()
            if fmt == 'geojson':
                ext = '.geojson'
                file_types = ('GeoJSON Files (*.geojson)',)
            elif fmt == 'json':
                ext = '.json'
                file_types = ('JSON Files (*.json)',)
            else:
                fmt = 'csv'
                ext = '.csv'
                file_types = ('CSV Files (*.csv)',)

            filename = payload.get('filename', 'cluster')
            stem = Path(filename).stem
            save_default = f"{stem}{ext}"

            idx_list = payload.get('indices', [])
            if not idx_list and payload.get('clusters'):
                idx_list = payload['clusters'][0].get('indices', [])

            if not idx_list:
                return {'status': 'error', 'message': 'No events in selected cluster.'}

            method = payload.get('method', 'dbscan')
            params = payload.get('params', {})

            result = self._window().create_file_dialog(
                webview.FileDialog.SAVE,
                directory=str(Path.home()),
                save_filename=save_default,
                file_types=file_types,
            )

            if not result:
                return {'status': 'cancelled'}

            save_path = Path(result[0] if isinstance(result, (list, tuple)) else result)
            if save_path.suffix.lower() != ext:
                save_path = save_path.with_suffix(ext)

            if fmt == 'geojson':
                write_single_cluster_geojson(self._data, save_path, idx_list, method, params, cluster_name=save_path.stem)
            elif fmt == 'json':
                write_single_cluster_json(self._data, save_path, idx_list, method, params, cluster_name=save_path.stem)
            else:
                write_single_cluster_csv(self._data, save_path, idx_list, method, params)

            return {'status': 'success', 'filename': save_path.name, 'path': str(save_path), 'format': fmt}
        except Exception as e:
            logger.exception("Error exporting single cluster")
            return {'status': 'error', 'message': str(e)}

    def export_clusters_zip(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Export all cluster files (CSV, GeoJSON, or JSON) packaged into a single ZIP file via native Save dialog."""
        try:
            if not self._data:
                return {'status': 'error', 'message': 'No dataset loaded'}

            method, params, export_items = collect_cluster_export_items(payload, self._last_cluster_result)
            if not export_items:
                return {'status': 'error', 'message': 'No cluster data available to export.'}

            payload = payload or {}
            fmt = str(payload.get('format', 'csv')).lower().strip()
            if fmt == 'geojson':
                default_zip = "seismic_clusters_geojson.zip"
            elif fmt == 'json':
                default_zip = "seismic_clusters_json.zip"
            else:
                fmt = 'csv'
                default_zip = "seismic_clusters_csv.zip"

            result = self._window().create_file_dialog(
                webview.FileDialog.SAVE,
                directory=str(Path.home()),
                save_filename=default_zip,
                file_types=('ZIP Archives (*.zip)',),
            )

            if not result:
                return {'status': 'cancelled'}

            save_path = Path(result[0] if isinstance(result, (list, tuple)) else result)
            if not str(save_path).lower().endswith('.zip'):
                save_path = save_path.with_suffix('.zip')

            exported_count = write_clusters_zip(self._data, save_path, export_items, method, params, file_format=fmt)

            return {'status': 'success', 'count': exported_count, 'path': str(save_path), 'format': fmt}
        except Exception as e:
            logger.exception("Error exporting clusters ZIP")
            return {'status': 'error', 'message': str(e)}

