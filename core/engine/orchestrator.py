import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import numpy as np
import plotly.graph_objects as go

from core.config import MESH_HD_SIZE, store_session_data
from core.engine.analysis import auto_tune_dbscan_params, auto_tune_kmeans_params
from core.engine.visualization import (
    get_3d_animated_figure,
    get_3d_cluster_figure,
    get_3d_static_figure,
    get_3d_subcluster_figure,
    view_2d,
)
from core.geo_utils import build_map_mesh
from core.network import is_osm_online
from core.templates import generate_html

logger = logging.getLogger(__name__)

def strip_data(fig_obj: go.Figure, data_dict: dict[str, Any]) -> None:
    """Removes heavy numerical data from seismic traces but PRESERVES the map mesh."""
    for trace in fig_obj.data:
        is_surface = isinstance(trace, go.Surface)
        is_structural = getattr(trace, 'name', '') in ['Map Terrain', 'Structural Planes', 'Coastline']
        
        if not (is_surface or is_structural):
            if hasattr(trace, 'x') and isinstance(trace.x, (list, np.ndarray)):
                trace.x = []
            if hasattr(trace, 'y') and isinstance(trace.y, (list, np.ndarray)):
                trace.y = []
            if hasattr(trace, 'z') and isinstance(trace.z, (list, np.ndarray)):
                trace.z = []
    
    keys_to_strip = [
        'longitude', 'latitude', 'magnitude', 'depth', 'dates_num', 
        'lon', 'lat', 'mag', 'dep', 'dnum', 'hover', 'cluster'
    ]
    for k in keys_to_strip:
        if k in data_dict:
            data_dict[k] = []

def _build_base_earthquake_dict(data: dict[str, Any], vpack: dict[str, Any], times: list[str]) -> dict[str, Any]:
    """Prepare the standardized earthquake data dictionary with visual limits and hover metadata.

    NOTE: Intentionally uses shallow copy (dict.copy()) — the contained NumPy arrays
    are read-only in the downstream JS-serialization workflow.  A deep copy would waste
    ~50MB of RAM for no benefit.  If future code needs to mutate array values in the
    copy, switch to copy.deepcopy() or explicit array slicing.
    """
    earthquake_data = data.copy()
    earthquake_data.update({
        'hover': vpack.get('hover', []),
        'mag_limit': vpack.get('mag_range', [0, 10]),
        'date_limit': vpack.get('date_range', [0, 0]),
        'dep_limit': vpack.get('dep_range', [0, 0]),
        'start_date': times[0][:10] if times else ""
    })
    return earthquake_data

def build_view_html(
    data: dict[str, Any], 
    view_style: int, 
    on_progress: Callable[[str], None] | None = None,
    anim_mode: str = 'accumulation', 
    window_days: int = 30, 
    step_days: int = 7,
    clustering_method: str = 'dbscan',
    clustering_params: dict[str, Any] | None = None,
    data_url: str = "", 
    session_id: str = "",
    **kwargs
) -> tuple[str, bool]:
    """Orchestrate view generation and return final HTML."""
    
    def _report(msg):
        if on_progress:
            on_progress(msg)

    lon, lat, mag, dep, times = data['longitude'], data['latitude'], data['magnitude'], data['depth'], data['times']
    d_num = data.get('dates_num', [])
    vpack = data.get('visual_pack', {})

    is_fallback = False
    bbox = data.get('bbox')
    if bbox is None:
        bbox = (float(np.min(lat)), float(np.min(lon)), float(np.max(lat)), float(np.max(lon)))
    data['bbox'] = bbox

    # 1. Prepare Map Mesh
    map_grids = None
    if view_style in (1, 2, 3, 4):
        _report("Preparing map mesh…")
        map_grids = build_map_mesh(bbox, MESH_HD_SIZE)
        is_fallback = (map_grids[5] is None) 
        
        x_g, y_g = map_grids[0], map_grids[1]
        graph_min_depth = float(np.floor(np.min(dep))) if len(dep) > 0 else 0.0
        data['graph_bounds'] = [
            float(np.min(y_g)), float(np.min(x_g)), 
            float(np.max(y_g)), float(np.max(x_g)), 
            graph_min_depth
        ]

    # 2. View Routing
    if view_style == 0:
        _report("Generating 2D map…")
        is_fallback = not is_osm_online()

        fig = view_2d(
            lon, lat, mag, times, 
            dates_num=d_num, depth=dep, visual_pack=vpack,
            origin_lat=data.get('origin_lat'), origin_lon=data.get('origin_lon')
        )
        earthquake_data = _build_base_earthquake_dict(data, vpack, times)
        
        if session_id:
            store_session_data(session_id, earthquake_data.copy())
            strip_data(fig, earthquake_data)
        html = generate_html(fig, earthquake_data=earthquake_data, is_fallback=is_fallback, data_url=data_url)

    elif view_style == 1:
        _report("Rendering 3D static view…")
        fig = get_3d_static_figure(lon, lat, mag, dep, times, dates_num=d_num, bbox=bbox, visual_pack=vpack, map_grids=map_grids)
        earthquake_data = _build_base_earthquake_dict(data, vpack, times)

        if session_id:
            store_session_data(session_id, earthquake_data.copy())
            strip_data(fig, earthquake_data)
        html = generate_html(fig, is_3d=True, earthquake_data=earthquake_data, is_fallback=is_fallback, data_url=data_url)

    elif view_style == 2:
        fig, anim_data = get_3d_animated_figure(lon, lat, mag, dep, times, on_progress=on_progress, anim_mode=anim_mode, window_days=window_days, step_days=step_days, data=data, bbox=bbox, map_grids=map_grids)
        if session_id:
            store_session_data(session_id, anim_data.copy())
            strip_data(fig, anim_data)
        html = generate_html(fig, is_animated=True, is_3d=True, earthquake_data=anim_data, is_fallback=is_fallback, data_url=data_url)

    elif view_style == 3:
        if clustering_params is None:
            clustering_params = {}
        if clustering_method == 'dbscan':
            auto_tune_dbscan_params(np.array(lon), np.array(lat), np.array(dep), data, clustering_params)
        elif clustering_method == 'kmeans':
            auto_tune_kmeans_params(np.array(lon), np.array(lat), np.array(dep), data, clustering_params)

        fig, labels, n_clusters = get_3d_cluster_figure(
            lon, lat, mag, dep, clustering_method=clustering_method, clustering_params=clustering_params, 
            bbox=bbox, visual_pack=vpack, map_grids=map_grids,
            origin_lat=data.get('origin_lat'), origin_lon=data.get('origin_lon'),
            depth_is_missing=data.get('depth_is_missing'),
            dates_num=data.get('dates_num', data.get('dnum'))
        )
        
        cluster_indices_dd = defaultdict(list)
        for i, lbl in enumerate(labels):
            cluster_indices_dd[int(lbl)].append(int(i))
        cluster_indices = dict(cluster_indices_dd)

        cluster_data = data.copy()
        cluster_data.update({
            'cluster': labels.tolist(),
            'cluster_indices': cluster_indices,
            'hover': vpack.get('hover', []),
            'mag_limit': vpack.get('mag_range', [0, 10]),
            'date_limit': vpack.get('date_range', [0, 0]),
            'dep_limit': vpack.get('dep_range', [0, 0]),
            'n_clusters': n_clusters,
            'clustering_method': clustering_method,
            'clustering_params': clustering_params,
            'start_date': times[0][:10] if times else ""
        })

        if session_id:
            store_session_data(session_id, cluster_data.copy())
            strip_data(fig, cluster_data)
        html = generate_html(fig, is_cluster=True, is_3d=True, earthquake_data=cluster_data, is_fallback=is_fallback, data_url=data_url)

    elif view_style == 4:
        target_indices = kwargs.get('target_indices', [])
        context_indices = kwargs.get('context_indices', None)
        locked_clusters = kwargs.get('locked_clusters', None)

        locked_set = {int(idx) for idxs in locked_clusters.values() for idx in idxs} if locked_clusters else set()
        unlocked_targets = [int(idx) for idx in target_indices if int(idx) not in locked_set]
        if not unlocked_targets:
            unlocked_targets = list(target_indices)
        
        # --- Calculate Optimal Parameters for Sub-cluster using ONLY unlocked points ---
        clustering_params = kwargs.get('clustering_params')
        if clustering_params is None:
            clustering_params = kwargs['clustering_params'] = {}

        unlocked_lon = np.asarray(lon)[unlocked_targets]
        unlocked_lat = np.asarray(lat)[unlocked_targets]
        unlocked_dep = np.asarray(dep)[unlocked_targets]

        sub_data = dict(data)
        if 'depth_is_missing' in data and data['depth_is_missing'] is not None:
            dim = np.asarray(data['depth_is_missing'])
            if len(dim) == len(lon):
                sub_data['depth_is_missing'] = dim[unlocked_targets]
        if 'dates_num' in data and data['dates_num'] is not None:
            dim_t = np.asarray(data['dates_num'])
            if len(dim_t) == len(lon):
                sub_data['dates_num'] = dim_t[unlocked_targets]

        if clustering_method == 'dbscan' and len(unlocked_targets) >= 5:
            auto_tune_dbscan_params(unlocked_lon, unlocked_lat, unlocked_dep, sub_data, clustering_params)
        elif clustering_method == 'kmeans' and len(unlocked_targets) >= 3:
            auto_tune_kmeans_params(unlocked_lon, unlocked_lat, unlocked_dep, sub_data, clustering_params)
        # -------------------------------------------------------------------------

        fig, full_labels, n_clusters, locked_cluster_ids = get_3d_subcluster_figure(
            lon, lat, mag, dep, target_indices, context_indices=context_indices,
            clustering_method=clustering_method, clustering_params=clustering_params, 
            bbox=bbox, visual_pack=vpack, map_grids=map_grids,
            origin_lat=data.get('origin_lat'), origin_lon=data.get('origin_lon'),
            locked_clusters=locked_clusters,
            dates_num=data.get('dates_num', data.get('dnum'))
        )

        cluster_indices_dd = defaultdict(list)
        for i, lbl in enumerate(full_labels):
            cluster_indices_dd[int(lbl)].append(int(i))
        cluster_indices = dict(cluster_indices_dd)

        cluster_data = data.copy()
        all_target_indices = sorted(list(set(target_indices) | locked_set)) if locked_set else list(target_indices)
        cluster_data.update({
            'cluster': full_labels.tolist(),
            'cluster_indices': cluster_indices,
            'locked_cluster_ids': locked_cluster_ids,
            'hover': vpack.get('hover', []),
            'mag_limit': vpack.get('mag_range', [0, 10]),
            'date_limit': vpack.get('date_range', [0, 0]),
            'dep_limit': vpack.get('dep_range', [0, 0]),
            'n_clusters': n_clusters,
            'clustering_method': clustering_method,
            'clustering_params': clustering_params,
            'subcluster_target_indices': all_target_indices,
            'subcluster_context_indices': context_indices,
            'start_date': times[0][:10] if times else ""
        })

        if session_id:
            store_session_data(session_id, cluster_data.copy())
            strip_data(fig, cluster_data)
        html = generate_html(fig, is_cluster=True, is_3d=True, earthquake_data=cluster_data, is_fallback=is_fallback, data_url=data_url, is_subcluster=True)

    else:
        raise ValueError(f"Invalid view style: {view_style}")

    return html, is_fallback
