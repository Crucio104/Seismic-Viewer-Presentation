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
    get_3d_animated_figure, get_cluster_update_traces,
    get_3d_subcluster_figure
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
        fig, labels, n_clusters = get_3d_cluster_figure(
            lon, lat, mag, dep, clustering_method=clustering_method, clustering_params=clustering_params, 
            bbox=bbox, visual_pack=vpack, map_grids=map_grids,
            origin_lat=data.get('origin_lat'), origin_lon=data.get('origin_lon')
        )
        
        cluster_indices = {}
        for i, lbl in enumerate(labels):
            if lbl >= 0:
                lbl_int = int(lbl)
                if lbl_int not in cluster_indices:
                    cluster_indices[lbl_int] = []
                cluster_indices[lbl_int].append(int(i))

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
        html = generate_html(fig, is_cluster=True, is_3d=True, back_button=back_button, earthquake_data=cluster_data, is_fallback=is_fallback, data_url=data_url)

    elif view_style == 4:
        target_indices = kwargs.get('target_indices', [])
        context_indices = kwargs.get('context_indices', None)
        
        # --- Calculate Optimal Epsilon for Sub-cluster using k-distance elbow ---
        if clustering_method == 'dbscan' and clustering_params is not None and len(target_indices) >= 5:
            try:
                from core.engine.analysis import project_to_km
                from sklearn.neighbors import NearestNeighbors
                
                target_lon = np.array(lon)[target_indices]
                target_lat = np.array(lat)[target_indices]
                target_dep = np.array(dep)[target_indices]
                
                o_lat = data.get('origin_lat', np.mean(target_lat))
                o_lon = data.get('origin_lon', np.mean(target_lon))
                
                pts_km = project_to_km(target_lon, target_lat, target_dep, o_lat, o_lon)
                n_pts = len(pts_km)
                
                # --- Heuristic for Min Samples in 3D ---
                # rimosso il limite di 6 su richiesta dell'utente. Usiamo un minimo tecnico di 3.
                optimal_min_samples = max(3, int(np.log(n_pts))) if n_pts > 0 else 3
                clustering_params['dbscan_min_samples'] = optimal_min_samples
                min_samples = optimal_min_samples
                
                if len(pts_km) > min_samples:
                    nn = NearestNeighbors(n_neighbors=min_samples)
                    nn.fit(pts_km)
                    distances, _ = nn.kneighbors(pts_km)
                    
                    k_dists = np.sort(distances[:, -1])
                    
                    # Find elbow (max distance to secant line)
                    n_points = len(k_dists)
                    all_coord = np.vstack((np.arange(n_points), k_dists)).T
                    first_point = all_coord[0]
                    line_vec = all_coord[-1] - first_point
                    norm_val = np.linalg.norm(line_vec)
                    if norm_val > 0:
                        line_vec_norm = line_vec / norm_val
                        
                        vec_from_first = all_coord - first_point
                        scalar_proj = np.sum(vec_from_first * line_vec_norm, axis=1)
                        vec_proj = np.outer(scalar_proj, line_vec_norm)
                        vec_to_line = vec_from_first - vec_proj
                        dist_to_line = np.linalg.norm(vec_to_line, axis=1)
                        
                        elbow_idx = np.argmax(dist_to_line)
                        optimal_eps_km = k_dists[elbow_idx]
                        
                        # Convert to meters and round to nearest 10
                        optimal_eps_m = int(round((optimal_eps_km * 1000) / 10.0) * 10)
                        if optimal_eps_m < 10:
                            optimal_eps_m = 10
                            
                        clustering_params['dbscan_eps'] = optimal_eps_m
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to calculate optimal eps: {e}")
        # -------------------------------------------------------------------------

        fig, labels, n_clusters = get_3d_subcluster_figure(
            lon, lat, mag, dep, target_indices, context_indices=context_indices,
            clustering_method=clustering_method, clustering_params=clustering_params, 
            bbox=bbox, visual_pack=vpack, map_grids=map_grids,
            origin_lat=data.get('origin_lat'), origin_lon=data.get('origin_lon')
        )
        
        full_labels = np.full(len(lon), -1, dtype=int)
        if len(target_indices) > 0 and len(labels) == len(target_indices):
            full_labels[target_indices] = labels

        cluster_indices = {}
        for i, lbl in enumerate(full_labels):
            if lbl >= 0:
                lbl_int = int(lbl)
                if lbl_int not in cluster_indices:
                    cluster_indices[lbl_int] = []
                cluster_indices[lbl_int].append(int(i))

        cluster_data = data.copy()
        cluster_data.update({
            'cluster': full_labels.tolist(),
            'cluster_indices': cluster_indices,
            'hover': vpack.get('hover', []),
            'mag_limit': vpack.get('mag_range', [0, 10]),
            'date_limit': vpack.get('date_range', [0, 0]),
            'dep_limit': vpack.get('dep_range', [0, 0]),
            'n_clusters': n_clusters,
            'clustering_method': clustering_method,
            'clustering_params': clustering_params,
            'subcluster_target_indices': target_indices,
            'subcluster_context_indices': context_indices,
            'start_date': times[0][:10] if times else ""
        })

        if session_id:
            store_session_data(session_id, cluster_data.copy())
            strip_data(fig, cluster_data)
        html = generate_html(fig, is_cluster=True, is_3d=True, back_button=back_button, earthquake_data=cluster_data, is_fallback=is_fallback, data_url=data_url)

    else:
        raise ValueError(f"Invalid view style: {view_style}")

    return html, is_fallback