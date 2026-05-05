import logging
import socket
import numpy as np
import plotly.graph_objects as go
from typing import Any, Callable

# Core modules
from core.loader import load_csv
from core.geo_utils import build_map_mesh
from core.config import MESH_HD_SIZE, store_session_data
from core.templates import generate_html

# Sub-engine modules
from core.engine.visualization import (
    view_2d, get_3d_static_figure, get_3d_cluster_figure, 
    get_3d_animated_figure, get_cluster_update_traces
)
from core.engine.analysis import (
    get_animation_planes, get_animation_clustering
)

logger = logging.getLogger(__name__)

# Re-exporting functions for backward compatibility if needed, 
# though internally we should migrate to direct imports.
__all__ = [
    'load_csv', 'build_view_html', 'strip_data', 
    'get_cluster_update_traces', 'get_animation_planes', 'get_animation_clustering'
]

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

def build_view_html(
    data: dict[str, Any], 
    view_style: int, 
    back_button: bool = True, 
    on_progress: Callable[[str], None] | None = None,
    anim_mode: str = 'accumulation', 
    window_days: int = 5, 
    clustering_method: str = 'kmeans',
    clustering_params: dict[str, Any] | None = None,
    data_url: str = "", 
    session_id: str = ""
) -> tuple[str, bool]:
    """Orchestrate view generation and return final HTML."""
    
    def _report(msg):
        if on_progress:
            on_progress(msg)

    lon, lat, mag, dep, times = data['longitude'], data['latitude'], data['magnitude'], data['depth'], data['times']
    d_num = data.get('dates_num', [])
    vpack = data.get('visual_pack', {})

    is_fallback = False
    bbox = data.get('bbox') or (min(lat), min(lon), max(lat), max(lon))
    data['bbox'] = bbox

    # 1. Prepare Map Mesh
    map_grids = None
    if view_style in [1, 2, 3]:
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
        try:
            socket.create_connection(("a.tile.openstreetmap.org", 80), timeout=1.0)
            is_fallback = False
        except Exception:
            is_fallback = True

        fig = view_2d(lon, lat, mag, times, dates_num=d_num, depth=dep, visual_pack=vpack)
        earthquake_data = data.copy()
        earthquake_data.update({
            'hover': vpack.get('hover', []),
            'mag_limit': vpack.get('mag_range', [0, 10]),
            'date_limit': vpack.get('date_range', [0, 0]),
            'dep_limit': vpack.get('dep_range', [0, 0]),
            'start_date': times[0][:10] if times else ""
        })
        
        if session_id:
            store_session_data(session_id, earthquake_data.copy())
            strip_data(fig, earthquake_data)
        html = generate_html(fig, back_button=back_button, earthquake_data=earthquake_data, is_fallback=is_fallback, data_url=data_url)

    elif view_style == 1:
        _report("Rendering 3D static view…")
        fig = get_3d_static_figure(lon, lat, mag, dep, times, dates_num=d_num, bbox=bbox, visual_pack=vpack, map_grids=map_grids)
        earthquake_data = data.copy()
        earthquake_data.update({
            'hover': vpack.get('hover', []),
            'mag_limit': vpack.get('mag_range', [0, 10]),
            'date_limit': vpack.get('date_range', [0, 0]),
            'dep_limit': vpack.get('dep_range', [0, 0]),
            'start_date': times[0][:10] if times else ""
        })

        if session_id:
            store_session_data(session_id, earthquake_data.copy())
            strip_data(fig, earthquake_data)
        html = generate_html(fig, is_3d=True, back_button=back_button, earthquake_data=earthquake_data, is_fallback=is_fallback, data_url=data_url)

    elif view_style == 2:
        fig, anim_data = get_3d_animated_figure(lon, lat, mag, dep, times, on_progress=on_progress, anim_mode=anim_mode, window_days=window_days, data=data, bbox=bbox, map_grids=map_grids)
        if session_id:
            store_session_data(session_id, anim_data.copy())
            strip_data(fig, anim_data)
        html = generate_html(fig, is_animated=True, is_3d=True, back_button=back_button, earthquake_data=anim_data, is_fallback=is_fallback, data_url=data_url)

    elif view_style == 3:
        fig, labels, n_clusters = get_3d_cluster_figure(lon, lat, mag, dep, clustering_method=clustering_method, clustering_params=clustering_params, bbox=bbox, visual_pack=vpack, map_grids=map_grids)
        cluster_data = data.copy()
        cluster_data.update({
            'cluster': labels.tolist(),
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
        html = generate_html(fig, is_cluster=True, is_3d=True, back_button=back_button, earthquake_data=cluster_data, is_fallback=is_fallback, data_url=data_url)

    else:
        raise ValueError(f"Invalid view style: {view_style}")

    return html, is_fallback