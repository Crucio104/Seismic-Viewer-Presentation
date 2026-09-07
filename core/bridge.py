from pathlib import Path
import uuid
import threading
import webview
import logging
import numpy as np
import asyncio
import time
import pandas as pd
import base64
import shutil
from collections import Counter, defaultdict
from typing import Any, Callable

from core.config import (
    BASE_DIR, get_http_port, 
    clear_session_data, TEMP_DIR, store_viz_html,
    MAP_CACHE_DIR, get_session_data, cleanup_temp_files
)
from core.history import get_recent_files, save_recent_file, clear_history
from core.online_importer import fetch_ingv_data
from core.geo_utils import build_map_mesh
from core.layer_utils import process_tomography_data, process_uplift_data, process_stations_data
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
        self._html_cache: dict[tuple, str] = {} 
        self._history_stack: list[dict[str, Any]] = []
        self._history_idx: int = -1
        self._socket_manager: object | None = None
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._last_cluster_result: dict[str, Any] | None = None

    def set_socket_manager(self, manager: object, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Set the FastAPI WebSocket manager and the event loop."""
        self._socket_manager = manager
        self._event_loop = loop

    # --- Internal Helpers ---

    def _make_url(self, viz_id: str) -> str:
        return f'http://127.0.0.1:{get_http_port()}/viz/{viz_id}'

    def _make_data_url(self, session_id: str) -> str:
        return f'http://127.0.0.1:{get_http_port()}/api/data/{session_id}'

    def clear_history(self) -> dict:
        """Clear all history sessions and caches."""
        self._history_stack.clear()
        self._history_idx = -1
        self._html_cache.clear()
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

    def save_screenshot(self, base64_data: str) -> dict[str, Any]:
        """Open native save dialog and write the base64 image data to a file."""
        try:
            # Open save file dialog
            result = self._window().create_file_dialog(
                webview.FileDialog.SAVE,
                directory=str(Path.home()),
                save_filename='seismic_viewer_export.png',
                file_types=('PNG Image (*.png)',),
            )
            
            if not result:
                return {'status': 'cancelled'}
            
            save_path = result[0] if isinstance(result, (list, tuple)) else result
            
            # Decode base64 data
            header, encoded = base64_data.split(",", 1)
            data = base64.b64decode(encoded)
            
            # Write to file
            with open(save_path, 'wb') as f:
                f.write(data)
                
            return {'status': 'success', 'path': save_path}
        except Exception as e:
            logger.error("Error in save_screenshot", exc_info=True)
            return {'error': str(e)}

    def save_current_csv(self) -> dict[str, Any]:
        """Open native save dialog and save a copy of the currently loaded dataset CSV."""
        try:
            if not self._csv_path or not Path(self._csv_path).exists():
                return {'error': 'No dataset loaded or file not found.'}

            original_filename = Path(self._csv_path).name
            if not original_filename.lower().endswith('.csv'):
                original_filename += '.csv'

            result = self._window().create_file_dialog(
                webview.FileDialog.SAVE,
                directory=str(Path.home()),
                save_filename=original_filename,
                file_types=('CSV Files (*.csv)',),
            )

            if not result:
                return {'status': 'cancelled'}

            save_path = result[0] if isinstance(result, (list, tuple)) else result
            save_path = str(save_path)
            if not save_path.lower().endswith('.csv'):
                save_path += '.csv'

            shutil.copy2(self._csv_path, save_path)
            logger.info(f"Dataset successfully saved to: {save_path}")
            save_recent_file(save_path)
            return {'status': 'success', 'path': save_path}
        except Exception as e:
            logger.error("Error in save_current_csv", exc_info=True)
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

            if self._csv_path is not None and self._csv_path != path:
                self._stored_layer_paths = {'stations': None, 'uplift': None, 'tomography': None}

            data = engine.load_csv(path)
            self._csv_path, self._data = path, data
            self._csv_info = {
                'filename': Path(path).name,
                'event_count': data['summary']['event_count'],
                'date_range': data['summary']['date_range'],
                'total_days': data['summary'].get('total_days', 365),
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

    def clear_recent_history(self) -> dict[str, Any]:
        """Clear recent files history and delete unsaved temporary INGV CSV downloads."""
        try:
            clear_history()
            cleanup_temp_files()
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
        self._history_stack.clear()
        self._history_stack.append({'view_style': view_style, 'kwargs': kwargs})
        self._history_idx = 0
        threading.Thread(target=self._generate_and_navigate, args=(view_style,), kwargs=kwargs, daemon=True).start()

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
        # Truncate future history if we diverge
        if self._history_idx >= 0:
            self._history_stack = self._history_stack[:self._history_idx + 1]
        
        self._history_stack.append({'view_style': 4, 'kwargs': kwargs})
        self._history_idx = len(self._history_stack) - 1
        threading.Thread(target=self._generate_and_navigate, args=(4,), kwargs=kwargs, daemon=True).start()

    def go_back(self) -> None:
        if self._history_idx > 0:
            self._history_idx -= 1
            prev = self._history_stack[self._history_idx]
            threading.Thread(target=self._generate_and_navigate, args=(prev['view_style'],), kwargs=prev['kwargs'], daemon=True).start()
        else:
            try:
                self._window().evaluate_js("transitionToHub()")
            except Exception:
                pass

    def go_forward(self) -> None:
        if self._history_idx < len(self._history_stack) - 1:
            self._history_idx += 1
            nxt = self._history_stack[self._history_idx]
            threading.Thread(target=self._generate_and_navigate, args=(nxt['view_style'],), kwargs=nxt['kwargs'], daemon=True).start()

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
            
            self._html_cache.clear()
            
            threading.Thread(target=self._generate_and_navigate, args=(prev_view['view_style'],), kwargs=prev_view['kwargs'], daemon=True).start()
            return {'status': 'success'}
        except Exception as e:
            logger.error("Apply subclusters failed", exc_info=True)
            return {'error': str(e)}

    def _generate_and_navigate(self, view_style: int, **kwargs) -> None:
        """Generate HTML and navigate the window."""
        try:
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
                self._window().load_url(url)
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
                if len(self._html_cache) >= 3:
                    self._html_cache.pop(next(iter(self._html_cache)))
                    import gc; gc.collect()
                if curr_history is not None:
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
            self._window().load_url(url)
            
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
            t1 = params.get('start_date', "").strip() if params.get('start_date') else ""
            t2 = params.get('end_date', "").strip() if params.get('end_date') else ""
            
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
                global_indices=global_indices
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
        self._html_cache.clear()
        clear_session_data()
        import gc; gc.collect()
        return True

    def clear_map_cache(self) -> bool | str:
        try:
            if MAP_CACHE_DIR.exists():
                shutil.rmtree(MAP_CACHE_DIR)
            MAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            
            self._html_cache.clear()
            build_map_mesh.cache_clear()
            clear_session_data()
            import gc; gc.collect()
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
                    
            stations_path = params.get('stations_path')
            if stations_path:
                self._stored_layer_paths['stations'] = {'path': str(stations_path), 'filename': Path(stations_path).name}
            if params.get('uplift_path'):
                self._stored_layer_paths['uplift'] = {'path': str(params['uplift_path']), 'filename': Path(params['uplift_path']).name}
            if params.get('tomography_path'):
                self._stored_layer_paths['tomography'] = {'path': str(params['tomography_path']), 'filename': Path(params['tomography_path']).name}

            if params.get('uplift_path'):
                uplift_res = process_uplift_data(params['uplift_path'], target_date_str=target_date, stations_path=stations_path)
                res['layers']['uplift'] = uplift_res
                
            if params.get('tomography_path'):
                tomo_res = process_tomography_data(params['tomography_path'])
                res['layers']['tomography'] = tomo_res
                
            if stations_path:
                stations_res = process_stations_data(stations_path)
                res['layers']['stations'] = stations_res
                
            import gc; gc.collect()
            return res
        except Exception as e:
            logger.error("Error in apply_external_layers", exc_info=True)
            return {'error': str(e)}

    def export_clusters_csv(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Export clustering results (each cluster + outliers) as CSV files to a chosen directory."""
        try:
            if not self._data:
                return {'status': 'error', 'message': 'No dataset loaded'}

            payload = payload or {}

            # Prioritize last stored cluster result for consistency of parameters and indices
            if self._last_cluster_result:
                res = self._last_cluster_result
                method = res.get('method', 'dbscan')
                params = res.get('params', {})
                cluster_indices = res.get('cluster_indices') or payload.get('cluster_indices')
                labels = res.get('labels') if res.get('labels') is not None else payload.get('labels')
            else:
                method = payload.get('method', 'dbscan')
                params = payload.get('params', {})
                cluster_indices = payload.get('cluster_indices')
                labels = payload.get('labels')

            # If we only have labels, build cluster_indices mapping
            if not cluster_indices and labels is not None:
                cluster_indices = defaultdict(list)
                for idx, lbl in enumerate(labels):
                    cluster_indices[int(lbl)].append(idx)

            if not cluster_indices:
                return {'status': 'error', 'message': 'No cluster data available to export. Please run clustering first.'}

            # Open folder selection dialog
            result = self._window().create_file_dialog(
                webview.FileDialog.FOLDER,
                directory=str(Path.home())
            )
            
            if not result:
                return {'status': 'cancelled'}
                
            save_dir = Path(result[0] if isinstance(result, (list, tuple)) else result)
            save_dir.mkdir(parents=True, exist_ok=True)

            # Extract full dataset arrays
            times = self._data.get('times', [])
            lats = self._data.get('latitude', [])
            lons = self._data.get('longitude', [])
            deps = self._data.get('depth', [])
            mags = self._data.get('magnitude', [])
            n_events = len(lons)

            # Format parameters string cleanly for header row
            if isinstance(params, dict):
                if str(method).lower() == 'dbscan':
                    eps = params.get('dbscan_eps') or params.get('eps') or params.get('eps_km', 'N/A')
                    min_samp = params.get('dbscan_min_samples') or params.get('min_samples', 'N/A')
                    param_str = f"eps={eps}, min_samples={min_samp}"
                elif str(method).lower() == 'kmeans':
                    n_clust = params.get('kmeans_clusters') or params.get('n_clusters') or params.get('kmeans_n_clusters', 'N/A')
                    max_d = params.get('kmeans_max_dist')
                    if max_d and float(max_d) > 0:
                        param_str = f"n_clusters={n_clust}, max_dist_m={max_d}"
                    else:
                        param_str = f"n_clusters={n_clust}"
                else:
                    param_str = ", ".join(f"{k}={v}" for k, v in params.items())
            else:
                param_str = str(params)

            header_comment = f"# Clustering Method: {str(method).upper()} | Parameters: {param_str}\n"

            exported_count = 0
            for lbl_str, idx_list in cluster_indices.items():
                if not idx_list:
                    continue
                
                lbl_int = int(lbl_str)
                if lbl_int == -1:
                    file_name = "outliers.csv"
                else:
                    file_name = f"cluster_{lbl_int}.csv"
                
                file_path = save_dir / file_name

                # Filter valid indices within bounds
                valid_indices = [int(i) for i in idx_list if 0 <= int(i) < n_events]
                if not valid_indices:
                    continue

                row_data = {
                    'time': [times[i] if i < len(times) else '' for i in valid_indices],
                    'latitude': [lats[i] for i in valid_indices],
                    'longitude': [lons[i] for i in valid_indices],
                    'depth': [abs(deps[i]) if i < len(deps) else 0.0 for i in valid_indices],
                    'magnitude': [mags[i] if i < len(mags) else 0.0 for i in valid_indices]
                }
                df = pd.DataFrame(row_data)

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(header_comment)
                    df.to_csv(f, index=False)
                
                exported_count += 1

            return {'status': 'success', 'count': exported_count, 'folder': str(save_dir)}
        except Exception as e:
            logger.error("Error exporting clusters CSV", exc_info=True)
            return {'status': 'error', 'message': str(e)}

