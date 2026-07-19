import logging
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.colors import qualitative as _pq
from scipy.spatial import ConvexHull
from typing import Any, Callable
from datetime import datetime, timedelta

from core.geo_utils import build_map_mesh
from core.config import MESH_HD_SIZE, KM_PER_DEGREE
from .analysis import fit_plane_ransac, get_strike_dip, perform_clustering

logger = logging.getLogger(__name__)

# --- Visual Constants ---

COMMON_LAYOUT = dict(
    autosize=True,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=0, r=0, b=0, t=0),
    showlegend=False,
    uirevision='constant'
)

def apply_3d_style(fig: go.Figure, x_range: list[float], y_range: list[float], z_range: list[float]) -> None:
    """Unified style application for 3D scenes with proportional aspect ratio."""
    lon_dist = abs(x_range[1] - x_range[0])
    lat_dist = abs(y_range[1] - y_range[0])
    
    avg_lat = (y_range[0] + y_range[1]) / 2
    lon_km = lon_dist * KM_PER_DEGREE * np.cos(np.radians(avg_lat))
    lat_km = lat_dist * KM_PER_DEGREE
    
    max_hw = max(lon_km, lat_km)
    if max_hw == 0:
        max_hw = 1
    
    ratio_x = lon_km / max_hw
    ratio_y = lat_km / max_hw
    ratio_z = 0.5 

    fig.update_layout(
        **COMMON_LAYOUT,
        scene=dict(
            dragmode='turntable',
            camera=dict(
                eye=dict(x=1.25, y=1.25, z=1.25),
                center=dict(x=0, y=0, z=0)
            ),
            bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                title=dict(text='Longitude', font=dict(color='rgba(255,255,255,0.8)')),
                range=x_range, showspikes=False,
                gridcolor='rgba(255,255,255,0.1)', tickfont=dict(color='rgba(255,255,255,0.6)')
            ),
            yaxis=dict(
                title=dict(text='Latitude', font=dict(color='rgba(255,255,255,0.8)')),
                range=y_range, showspikes=False,
                gridcolor='rgba(255,255,255,0.1)', tickfont=dict(color='rgba(255,255,255,0.6)')
            ),
            zaxis=dict(
                title=dict(text='Depth (km)', font=dict(color='rgba(255,255,255,0.8)')),
                range=z_range, showspikes=False,
                gridcolor='rgba(255,255,255,0.1)', tickfont=dict(color='rgba(255,255,255,0.6)')
            ),
            aspectmode='manual',
            aspectratio=dict(x=ratio_x, y=ratio_y, z=ratio_z),
        )
    )

# --- View Generation ---

def view_2d(longitude: list[float], latitude: list[float], magnitude: list[float], times: list[str], dates_num: list[float] | None = None, depth: list[float] | None = None, visual_pack: dict[str, Any] | None = None) -> go.Figure:
    """Generate a 2D map view with scatter and density traces."""
    all_hover = visual_pack.get('hover', []) if visual_pack else []

    fig = px.scatter_mapbox(
        lat=latitude, lon=longitude,
        size=np.maximum(np.array(magnitude), 0.1),
        color=depth if depth is not None else magnitude,
        hover_name=all_hover,
        zoom=12,
        center=dict(
            lat=(min(latitude) + max(latitude)) / 2,
            lon=(min(longitude) + max(longitude)) / 2
        ),
        labels={"lat": "Latitude", "lon": "Longitude", "size": "Magnitude", "color": "Depth" if depth is not None else "Magnitude"},
    )
    
    fig.update_traces(
        marker=dict(coloraxis=None, colorscale='Viridis', showscale=False),
        hoverinfo='text',
        hovertemplate='%{hovertext}<extra></extra>',
        name='Earthquakes (Scatter)'
    )
    
    fig.add_trace(go.Densitymapbox(
        lat=latitude, lon=longitude, z=magnitude,
        radius=15, colorscale='Viridis',
        showscale=False, visible=False,
        name='Earthquakes (Heatmap)'
    ))
    
    if dates_num is not None:
        fig.data[0].customdata = np.array(dates_num).reshape(-1, 1)

    fig.update_layout(**COMMON_LAYOUT, mapbox_style="open-street-map")
    return fig

def get_3d_static_figure(
    longitude: list[float], latitude: list[float], magnitude: list[float], depth: list[float], times: list[str], 
    dates_num: list[float] | None = None, bbox: tuple[float, float, float, float] | None = None, 
    visual_pack: dict[str, Any] | None = None, map_grids: tuple[Any, ...] | None = None
) -> go.Figure:
    """Generate a high-quality 3D static view."""
    if bbox is None:
        bbox = (min(latitude), min(longitude), max(latitude), max(longitude))
    min_depth = np.floor(np.min(depth)) if len(depth) > 0 else 0

    if map_grids:
        x_grid, y_grid, z_grid, surfacecolor, colorscale, _ = map_grids
    else:
        x_grid, y_grid, z_grid, surfacecolor, colorscale, _ = build_map_mesh(bbox, MESH_HD_SIZE)

    all_hover = visual_pack.get('hover', []) if visual_pack else []
    fig = go.Figure()

    fig.add_trace(go.Surface(
        x=x_grid, y=y_grid, z=z_grid,
        surfacecolor=surfacecolor, colorscale=colorscale,
        showscale=False, opacity=0.9, hoverinfo='skip',
        lighting=dict(ambient=1, diffuse=0, specular=0, roughness=1, fresnel=0)
    ))

    fig.add_trace(go.Scatter3d(
        x=longitude, y=latitude, z=depth, mode='markers', hovertext=all_hover,
        marker=dict(
            size=5, color=depth, colorscale='Viridis', showscale=False,
            cmin=min(depth), cmax=max(depth),
            line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
            opacity=0.9,
        ),
        name='Earthquakes (Depth)', visible=True, showlegend=False, hovertemplate='%{hovertext}<extra></extra>'
    ))

    if dates_num is not None:
        fig.add_trace(go.Scatter3d(
            x=longitude, y=latitude, z=depth, mode='markers', hovertext=all_hover,
            marker=dict(
                size=5, color=dates_num, colorscale='Jet', showscale=False,
                cmin=min(dates_num), cmax=max(dates_num),
                line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
                opacity=0.9,
            ),
            name='Earthquakes (Date)', visible=False, showlegend=False, hovertemplate='%{hovertext}<extra></extra>'
        ))
    else:
        fig.add_trace(go.Scatter3d(x=[], y=[], z=[], visible=False, hoverinfo='skip'))

    apply_3d_style(fig, [x_grid[0], x_grid[-1]], [y_grid[-1], y_grid[0]], [min_depth, 0])
    return fig

def get_3d_cluster_figure(longitude: list[float], latitude: list[float], magnitude: list[float], depth: list[float],
                            clustering_method: str = 'dbscan', clustering_params: dict[str, Any] | None = None,
                            bbox: tuple[float, float, float, float] | None = None, visual_pack: dict[str, Any] | None = None, 
                            map_grids: tuple[Any, ...] | None = None,
                            origin_lat: float | None = None, origin_lon: float | None = None) -> tuple[go.Figure, np.ndarray, int]:
    """Generate the initial high-quality 3D Cluster figure."""
    min_depth = np.floor(np.min(depth)) if len(depth) > 0 else 0
    if bbox is None:
        bbox = (np.min(latitude), np.min(longitude), np.max(latitude), np.max(longitude))

    if map_grids:
        x_grid, y_grid, z_grid, surfacecolor, colorscale, _ = map_grids
    else:
        x_grid, y_grid, z_grid, surfacecolor, colorscale, _ = build_map_mesh(bbox, MESH_HD_SIZE)

    result = _generate_cluster_traces(
        longitude, latitude, magnitude, depth, 
        visual_pack.get('hover', []) if visual_pack else [],
        clustering_method, clustering_params, viz_mask=None,
        origin_lat=origin_lat, origin_lon=origin_lon
    )
    
    fig = go.Figure()
    fig.add_trace(go.Surface(
        x=x_grid, y=y_grid, z=z_grid,
        surfacecolor=surfacecolor, colorscale=colorscale,
        showscale=False, opacity=0.9, hoverinfo='skip',
        lighting=dict(ambient=1, diffuse=0, specular=0, roughness=1, fresnel=0)
    ))

    for t in result['traces']:
        fig.add_trace(t)

    apply_3d_style(fig, [x_grid[0], x_grid[-1]], [y_grid[-1], y_grid[0]], [min_depth, 0])
    return fig, result['labels'], result['n_clusters']


def get_3d_subcluster_figure(
    longitude: list[float], latitude: list[float], magnitude: list[float], depth: list[float], 
    target_indices: list[int], context_indices: list[int] | None = None,
    clustering_method: str = 'dbscan', clustering_params: dict[str, Any] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    visual_pack: dict[str, Any] | None = None, map_grids: tuple | None = None,
    origin_lat: float | None = None, origin_lon: float | None = None,
    locked_clusters: dict[int, list[int]] | None = None
) -> tuple[go.Figure, np.ndarray, int, list[int]]:
    
    n_points = len(longitude)
    full_labels = np.full(n_points, -1, dtype=int)
    locked_mask = np.zeros(n_points, dtype=bool)
    locked_ids: set[int] = set()

    if locked_clusters:
        for k, idxs in locked_clusters.items():
            lbl_id = int(k)
            locked_ids.add(lbl_id)
            for idx in idxs:
                if 0 <= int(idx) < n_points:
                    full_labels[int(idx)] = lbl_id
                    locked_mask[int(idx)] = True

    # Only subcluster points in target_indices that are NOT locked
    unlocked_targets = [idx for idx in target_indices if 0 <= int(idx) < n_points and not locked_mask[int(idx)]]

    if len(unlocked_targets) > 0:
        sub_lon = np.array([longitude[i] for i in unlocked_targets], dtype=float)
        sub_lat = np.array([latitude[i] for i in unlocked_targets], dtype=float)
        _sub_mag = np.array([magnitude[i] for i in unlocked_targets], dtype=float)
        sub_dep = np.array([depth[i] for i in unlocked_targets], dtype=float)

        if origin_lat is None:
            origin_lat = float(np.mean(latitude))
        if origin_lon is None:
            origin_lon = float(np.mean(longitude))

        from .analysis import project_to_km
        X_km = project_to_km(sub_lon, sub_lat, sub_dep, origin_lat, origin_lon)
        local_labels, n_local, _ = perform_clustering(X_km, clustering_method, clustering_params or {})

        # Map local cluster labels to global IDs starting from 0, skipping locked_ids
        local_to_global = {}
        next_id = 0
        for loc_id in range(n_local):
            while next_id in locked_ids:
                next_id += 1
            local_to_global[loc_id] = next_id
            next_id += 1

        for i, idx in enumerate(unlocked_targets):
            loc_lbl = int(local_labels[i])
            if loc_lbl >= 0:
                full_labels[idx] = local_to_global.get(loc_lbl, -1)
            else:
                full_labels[idx] = -1

    active_labels = full_labels[full_labels >= 0]
    n_clusters = int(np.max(active_labels)) + 1 if len(active_labels) > 0 else 0

    fig = go.Figure()

    # Add Map Surface
    min_depth = float(np.min(depth)) if len(depth) > 0 else 0
    if map_grids:
        x_grid, y_grid, z_grid_mesh, surfacecolor, colorscale, _ = map_grids
    else:
        from core.geo_utils import build_map_mesh
        from core.config import MESH_HD_SIZE
        if bbox is None:
            bbox = (np.min(latitude), np.min(longitude), np.max(latitude), np.max(longitude))
        x_grid, y_grid, z_grid_mesh, surfacecolor, colorscale, _ = build_map_mesh(bbox, MESH_HD_SIZE)

    fig.add_trace(go.Surface(
        x=x_grid, y=y_grid, z=z_grid_mesh,
        surfacecolor=surfacecolor, colorscale=colorscale,
        opacity=0.9, showscale=False,
        hoverinfo='skip', name='Map Terrain',
        lighting=dict(ambient=1, diffuse=0, specular=0, roughness=1, fresnel=0)
    ))

    # Add background points (Other Events: noise -1)
    bg_mask = (full_labels == -1)
    lon_bg = np.array(longitude)[bg_mask]
    lat_bg = np.array(latitude)[bg_mask]
    dep_bg = np.array(depth)[bg_mask]
    
    if len(lon_bg) > 0:
        point_size_mode = clustering_params.get('point_size_mode', 'uniform') if clustering_params else 'uniform'
        if point_size_mode == 'magnitude':
            mag_bg = np.array(magnitude)[bg_mask]
            bg_sizes = np.maximum(8, (np.maximum(0, mag_bg) ** 2) * 1.5).tolist()
        else:
            bg_sizes = 5

        fig.add_trace(go.Scatter3d(
            x=lon_bg.tolist(), y=lat_bg.tolist(), z=dep_bg.tolist(),
            mode='markers',
            marker=dict(
                size=bg_sizes,
                color='#888888',
                line=dict(width=1, color='rgba(50,50,50,0.8)'),
                opacity=0.9
            ),
            hoverinfo='skip',
            showlegend=False,
            name='Other Events'
        ))

    # Add cluster traces for all active clusters
    params_for_traces = dict(clustering_params or {})
    params_for_traces['custom_labels'] = full_labels.tolist()
    params_for_traces['preserve_labels'] = True

    result = _generate_cluster_traces(
        longitude, latitude, magnitude, depth,
        visual_pack.get('hover', []) if visual_pack else [],
        clustering_method, params_for_traces, viz_mask=(full_labels >= 0),
        origin_lat=origin_lat, origin_lon=origin_lon
    )

    for t in result['traces']:
        fig.add_trace(t)

    apply_3d_style(fig, [x_grid[0], x_grid[-1]], [y_grid[-1], y_grid[0]], [min_depth, 0])
    return fig, full_labels, n_clusters, sorted(list(locked_ids))

def get_cluster_update_traces(longitude: list[float], latitude: list[float], magnitude: list[float], depth: list[float], hover: list[str],
                               clustering_method: str = 'dbscan', clustering_params: dict[str, Any] | None = None, viz_mask: np.ndarray | None = None,
                               origin_lat: float | None = None, origin_lon: float | None = None, 
                               subcluster_target_mask: np.ndarray | None = None, subcluster_context_mask: np.ndarray | None = None,
                               global_indices: np.ndarray | None = None) -> dict[str, Any]:
    """Perform clustering and return a JSON-ready package for async updates."""
    actual_viz_mask = viz_mask
    if subcluster_target_mask is not None:
        if actual_viz_mask is not None:
            actual_viz_mask = actual_viz_mask & subcluster_target_mask
        else:
            actual_viz_mask = subcluster_target_mask

    result = _generate_cluster_traces(
        longitude, latitude, magnitude, depth, hover,
        clustering_method, clustering_params, actual_viz_mask,
        origin_lat=origin_lat, origin_lon=origin_lon, global_indices=global_indices
    )
    
    traces = result['traces']
    
    # Add context points if available, or if target mask is set
    if subcluster_context_mask is not None:
        bg_mask = subcluster_context_mask & (~actual_viz_mask)
    elif subcluster_target_mask is not None:
        bg_mask = ~subcluster_target_mask
        if viz_mask is not None:
            bg_mask = bg_mask & viz_mask
    else:
        bg_mask = None

    if bg_mask is not None:
        lon_bg = np.array(longitude)[bg_mask]
        lat_bg = np.array(latitude)[bg_mask]
        dep_bg = np.array(depth)[bg_mask]
        
        if len(lon_bg) > 0:
            point_size_mode = clustering_params.get('point_size_mode', 'uniform') if clustering_params else 'uniform'
            if point_size_mode == 'magnitude':
                mag_bg = np.array(magnitude)[bg_mask]
                bg_sizes = np.maximum(8, (np.maximum(0, mag_bg) ** 2) * 1.5).tolist()
            else:
                bg_sizes = 5

            bg_trace = go.Scatter3d(
                x=lon_bg.tolist(), y=lat_bg.tolist(), z=dep_bg.tolist(),
                mode='markers',
                marker=dict(
                    size=bg_sizes,
                    color='#888888',
                    line=dict(width=1, color='rgba(50,50,50,0.8)'),
                    opacity=0.9
                ),
                hoverinfo='skip',
                showlegend=False,
                name='Other Events'
            )
            traces.insert(0, bg_trace)

    json_traces = [t.to_plotly_json() for t in traces]
    
    # Build cluster_indices mapping global indices to labels
    # actual_viz_mask indicates which points were clustered
    cluster_indices = {}
    if actual_viz_mask is not None:
        global_idx = np.where(actual_viz_mask)[0]
        for i, lbl in enumerate(result['labels']):
            lbl_int = int(lbl)
            if lbl_int not in cluster_indices:
                cluster_indices[lbl_int] = []
            cluster_indices[lbl_int].append(int(global_idx[i]))
    else:
        for i, lbl in enumerate(result['labels']):
            lbl_int = int(lbl)
            if lbl_int not in cluster_indices:
                cluster_indices[lbl_int] = []
            cluster_indices[lbl_int].append(i)
                
    return {
        'traces': json_traces,
        'labels': result['labels'].tolist() if hasattr(result['labels'], 'tolist') else list(result['labels']),
        'n_clusters': result['n_clusters'],
        'cluster_indices': cluster_indices
    }

def _generate_cluster_traces(longitude: list[float] | np.ndarray, latitude: list[float] | np.ndarray, magnitude: list[float] | np.ndarray, depth: list[float] | np.ndarray, hover: list[str],
                             method: str = 'dbscan', params: dict[str, Any] | None = None, viz_mask: np.ndarray | None = None,
                             origin_lat: float | None = None, origin_lon: float | None = None, global_indices: np.ndarray | None = None) -> dict[str, Any]:
    """Shared helper to perform clustering and generate Plotly trace objects."""
    params = params or {}
    longitude, latitude, depth = np.array(longitude), np.array(latitude), np.array(depth)
    magnitude = np.array(magnitude)
    
    if viz_mask is not None:
        m_idx = viz_mask
        f_lon, f_lat, f_dep = longitude[m_idx], latitude[m_idx], depth[m_idx]
        f_mag = magnitude[m_idx]
        f_hover = [hover[i] for i, val in enumerate(m_idx) if val and i < len(hover)]
    else:
        f_lon, f_lat, f_dep, f_mag, f_hover = longitude, latitude, depth, magnitude, hover

    if len(f_lon) == 0:
        return {'traces': [], 'labels': np.array([]), 'n_clusters': 0}

    # Use provided global origin if available, otherwise fallback to local mean
    if origin_lat is None:
        origin_lat = np.mean(f_lat)
    if origin_lon is None:
        origin_lon = np.mean(f_lon)
    
    from .analysis import project_to_km
    X_km = project_to_km(f_lon, f_lat, f_dep, origin_lat, origin_lon)
    X_orig_f = np.column_stack((f_lon, f_lat, f_dep))

    custom_labels = params.get('custom_labels') if params else None
    if custom_labels is not None:
        full_labels = np.array(custom_labels)
        if viz_mask is not None:
            display_labels = full_labels[viz_mask]
        else:
            display_labels = full_labels

        if params.get('preserve_labels', False):
            max_lbl = int(np.max(display_labels)) if len(display_labels) > 0 and np.any(display_labels >= 0) else -1
            n_clusters = max_lbl + 1
            labels = display_labels
        else:
            unique_l = sorted(list(set(display_labels[display_labels >= 0])))
            mapped_labels = np.full_like(display_labels, -1)
            for new_idx, old_idx in enumerate(unique_l):
                mapped_labels[display_labels == old_idx] = new_idx
                
            display_labels = mapped_labels
            n_clusters = len(unique_l)
            labels = display_labels
    else:
        locked_clusters = params.get('locked_clusters')
        if locked_clusters:
            display_labels = np.full(len(f_lon), -1, dtype=int)
            locked_mask = np.zeros(len(f_lon), dtype=bool)
            locked_ids = set()
            
            gidx_to_locked_lbl = {}
            for k, idxs in locked_clusters.items():
                lbl_id = int(k)
                locked_ids.add(lbl_id)
                for gidx in idxs:
                    gidx_to_locked_lbl[int(gidx)] = lbl_id

            for j in range(len(f_lon)):
                g_idx = int(global_indices[j]) if global_indices is not None else j
                if g_idx in gidx_to_locked_lbl:
                    display_labels[j] = gidx_to_locked_lbl[g_idx]
                    locked_mask[j] = True

            unlocked_indices = [j for j in range(len(f_lon)) if not locked_mask[j]]
            if len(unlocked_indices) > 0:
                local_labels, n_local, _ = perform_clustering(X_km[unlocked_indices], method, params)
                local_to_global = {}
                next_id = 0
                for loc_id in range(n_local):
                    while next_id in locked_ids:
                        next_id += 1
                    local_to_global[loc_id] = next_id
                    next_id += 1

                for idx_in_unlocked, j in enumerate(unlocked_indices):
                    loc_lbl = int(local_labels[idx_in_unlocked])
                    if loc_lbl >= 0:
                        display_labels[j] = local_to_global.get(loc_lbl, -1)
                    else:
                        display_labels[j] = -1

            active_labels = display_labels[display_labels >= 0]
            n_clusters = int(np.max(active_labels)) + 1 if len(active_labels) > 0 else 0
            labels = display_labels
        else:
            display_labels, n_clusters, _ = perform_clustering(X_km, method, params)
            labels = display_labels # For return consistency

    cluster_colors = _pq.Plotly
    traces = []

    # A. Geometry Traces: Wireframes
    for i in range(n_clusters):
        pts = X_orig_f[display_labels == i]
        traces.append(_get_cluster_hull_trace(pts, cluster_colors[i % len(cluster_colors)], i))

    # B. Geometry Traces: Solid Meshes
    for i in range(n_clusters):
        pts = X_orig_f[display_labels == i]
        traces.append(_get_cluster_mesh_trace(pts, cluster_colors[i % len(cluster_colors)], i))

    # C. Cluster Planes
    show_planes = params.get('show_cluster_planes', False)
    for i in range(n_clusters):
        pts = X_orig_f[display_labels == i]
        traces.append(_get_cluster_plane_trace(pts, cluster_colors[i % len(cluster_colors)], i, show_planes))

    # D. Earthquake Markers
    traces.append(_get_cluster_marker_trace(f_lon, f_lat, f_dep, f_mag, f_hover, display_labels, cluster_colors, params))

    # E. Centroids
    if method == 'kmeans':
        traces.append(_get_cluster_centroid_trace(X_orig_f, f_mag, labels, n_clusters))
    else:
        traces.append(go.Scatter3d(x=[], y=[], z=[], visible=False, showlegend=False))

    # F. Legend Proxies
    for i in range(n_clusters):
        is_visible = bool(np.any(display_labels == i))
        traces.append(go.Scatter3d(
            x=[None], y=[None], z=[None], mode='markers',
            marker=dict(color=cluster_colors[i % len(cluster_colors)], size=10),
            name=f'Cluster {i+1}', visible=is_visible, showlegend=is_visible
        ))

    return {'traces': traces, 'labels': labels, 'n_clusters': n_clusters}

def _get_cluster_hull_trace(pts: np.ndarray, color: str, index: int) -> go.Scatter3d:
    """Generate a wireframe hull for a cluster."""
    if len(pts) <= 4:
        return go.Scatter3d(x=[], y=[], z=[], visible=False, hoverinfo='skip')
    
    try:
        hull = ConvexHull(pts)
        lx, ly, lz = [], [], []
        for s in hull.simplices:
            for c in [(0,1), (1,2), (2,0)]:
                lx.extend([pts[s[c[0]], 0], pts[s[c[1]], 0], None])
                ly.extend([pts[s[c[0]], 1], pts[s[c[1]], 1], None])
                lz.extend([pts[s[c[0]], 2], pts[s[c[1]], 2], None])
        return go.Scatter3d(
            x=lx, y=ly, z=lz, mode='lines',
            line=dict(color=color, width=2),
            opacity=0.4, name=f'Cluster {index+1} Wire', visible=True, showlegend=False, hoverinfo='skip'
        )
    except Exception:
        return go.Scatter3d(x=[], y=[], z=[], visible=False, hoverinfo='skip')

def _get_cluster_mesh_trace(pts: np.ndarray, color: str, index: int) -> go.Mesh3d:
    """Generate a solid volume mesh for a cluster."""
    if len(pts) <= 4:
        return go.Mesh3d(x=[], y=[], z=[], visible=False, hoverinfo='skip')
    
    try:
        return go.Mesh3d(
            x=pts[:, 0].tolist(), y=pts[:, 1].tolist(), z=pts[:, 2].tolist(),
            color=color, opacity=0.15, alphahull=0,
            name=f'Cluster {index+1} Solid', visible=False, showlegend=False, hoverinfo='skip'
        )
    except Exception:
        return go.Mesh3d(x=[], y=[], z=[], visible=False, hoverinfo='skip')

def _get_cluster_plane_trace(pts: np.ndarray, color: str, index: int, visible: bool) -> go.Mesh3d:
    """Generate a structural plane for a cluster using RANSAC."""
    if len(pts) < 4:
        return go.Mesh3d(x=[], y=[], z=[], visible=False, hoverinfo='skip')
    
    origin_lat_c, origin_lon_c = np.mean(pts[:, 1]), np.mean(pts[:, 0])
    lon_to_km_c = KM_PER_DEGREE * np.cos(np.radians(origin_lat_c))
    pts_km_c = np.column_stack(((pts[:, 0] - origin_lon_c) * lon_to_km_c, (pts[:, 1] - origin_lat_c) * KM_PER_DEGREE, pts[:, 2]))
    
    normal, centroid_km, planarity = fit_plane_ransac(pts_km_c, threshold=0.15)
    if normal is None or centroid_km is None:
        return go.Mesh3d(x=[], y=[], z=[], visible=False, hoverinfo='skip')
        
    avg_dist = np.mean(np.linalg.norm(pts_km_c - centroid_km, axis=1))
    size = max(0.2, 5 * avg_dist)
    
    u = np.cross(normal, [0, 0, 1])
    if np.linalg.norm(u) < 1e-6:
        u = np.array([1, 0, 0])
    else:
        u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    v /= np.linalg.norm(v)
    
    grid_size_u, grid_size_v = 20, 15
    rect_verts_km = []
    i_idx, j_idx, k_idx = [], [], []
    for r in range(grid_size_u):
        for c in range(grid_size_v):
            u_f, v_f = (r / (grid_size_u - 1)) - 0.5, (c / (grid_size_v - 1)) - 0.5
            rect_verts_km.append(centroid_km + u_f * size * u + v_f * size * v)
    rect_verts_km = np.array(rect_verts_km)
    
    v_lon = (rect_verts_km[:, 0] / lon_to_km_c) + origin_lon_c
    v_lat = (rect_verts_km[:, 1] / KM_PER_DEGREE) + origin_lat_c
    rect_verts = np.column_stack((v_lon, v_lat, rect_verts_km[:, 2]))
    
    for r in range(grid_size_u - 1):
        for c in range(grid_size_v - 1):
            p1 = r * grid_size_v + c
            p2, p3, p4 = p1 + 1, p1 + grid_size_v, p1 + grid_size_v + 1
            i_idx.extend([p1, p2])
            j_idx.extend([p2, p4])
            k_idx.extend([p3, p3])
    
    strike, dip, dd = get_strike_dip(normal)
    c_lon = (centroid_km[0] / lon_to_km_c) + origin_lon_c
    c_lat = (centroid_km[1] / KM_PER_DEGREE) + origin_lat_c
    eq_a, eq_b, eq_c = normal[0]*lon_to_km_c, normal[1]*KM_PER_DEGREE, normal[2]
    eq_d = -(eq_a*c_lon + eq_b*c_lat + eq_c*centroid_km[2])
    hover_str = f"Cluster {index+1} Plane<br>Strike: {strike:.1f}°<br>Dip: {dip:.1f}°<br>Dip Dir: {dd:.1f}°<br>{eq_a:+.2f}x {eq_b:+.2f}y {eq_c:+.2f}z {eq_d:+.2f} = 0"
    
    return go.Mesh3d(
        x=rect_verts[:, 0].tolist(), y=rect_verts[:, 1].tolist(), z=rect_verts[:, 2].tolist(),
        i=i_idx, j=j_idx, k=k_idx, color=color, opacity=0.6,
        name=f'Cluster {index+1} Plane', visible=visible, showlegend=False,
        hoverinfo='text', text=[hover_str] * len(rect_verts),
        hoverlabel=dict(bgcolor=color, font=dict(color='white'))
    )

def _get_cluster_marker_trace(lon: np.ndarray, lat: np.ndarray, dep: np.ndarray, mag: np.ndarray, hover: list[str], labels: np.ndarray, colors: list[str], params: dict[str, Any]) -> go.Scatter3d:
    """Generate the earthquake marker trace with cluster coloring."""
    pt_colors = [colors[int(lbl) % len(colors)] if lbl >= 0 else '#888888' for lbl in labels]
    
    point_size_mode = params.get('point_size_mode', 'uniform')
    if point_size_mode == 'magnitude':
        sizes = np.maximum(8, (np.maximum(0, mag) ** 2) * 1.5).tolist()
    else:
        sizes = 5

    return go.Scatter3d(
        x=lon.tolist(), y=lat.tolist(), z=dep.tolist(), mode='markers', hovertext=hover,
        marker=dict(size=sizes, color=pt_colors, line=dict(width=1, color='rgba(50,50,50,0.8)'), opacity=0.9),
        name='Earthquakes', visible=True, showlegend=False, hovertemplate='%{hovertext}<extra></extra>'
    )

def _get_cluster_centroid_trace(pts_full: np.ndarray, mag: np.ndarray, labels: np.ndarray, n_clusters: int) -> go.Scatter3d:
    """Generate the centroid markers for KMeans clusters."""
    cx, cy, cz, ch = [], [], [], []
    for i in range(n_clusters):
        idx = (labels == i)
        if np.any(idx):
            m, am = np.mean(pts_full[idx], axis=0), np.mean(mag[idx])
            cx.append(m[0])
            cy.append(m[1])
            cz.append(m[2])
            ch.append(f"<b>Cluster {i+1} Centroid</b><br>Lat: {m[1]:.4f}<br>Lon: {m[0]:.4f}<br>Dep: {abs(m[2]):.2f}km<br>Avg Mag: {am:.2f}")
    return go.Scatter3d(
        x=cx, y=cy, z=cz, mode='markers', hovertext=ch,
        marker=dict(symbol='diamond', size=8, color='#ffffff', line=dict(width=2, color='#000')),
        name='Cluster Centroids', showlegend=True, visible=True, hovertemplate='%{hovertext}<extra></extra>'
    )

def get_3d_animated_figure(
    longitude: list[float], latitude: list[float], magnitude: list[float], depth: list[float], times: list[str],
    on_progress: Callable[[str], None] | None = None, anim_mode: str = 'accumulation', window_days: int = 30, step_days: int = 7,
    data: dict[str, Any] | None = None, bbox: tuple[float, float, float, float] | None = None, map_grids: tuple[Any, ...] | None = None
) -> tuple[go.Figure, dict[str, Any]]:
    """Generate a 3D figure for animation."""
    def _report(msg):
        logger.info(msg)
        if on_progress:
            on_progress(msg)

    _report("Preparing 3D animation data...")
    vpack = data.get('visual_pack', {})
    unique_dates = vpack.get('unique_dates', [])

    if bbox is None:
        bbox = (min(latitude), min(longitude), max(latitude), max(longitude))
    min_depth = np.floor(np.min(depth)) if len(depth) > 0 else 0

    if map_grids:
        x_high, y_high, z_high, mat_high, scale_high, map_data = map_grids
    else:
        _report("Building map mesh (HD)...")
        x_high, y_high, z_high, mat_high, scale_high, map_data = build_map_mesh(bbox, MESH_HD_SIZE)

    mag_range, date_range, dep_range = vpack.get('mag_range', [0, 10]), vpack.get('date_range', [0, 0]), vpack.get('dep_range', [0, 0])

    fig = go.Figure()
    fig.add_trace(go.Surface(
        x=x_high, y=y_high, z=z_high, surfacecolor=mat_high, colorscale=scale_high,
        showscale=False, opacity=0.85, hoverinfo='skip', visible=True,
        lighting=dict(ambient=1, diffuse=0, specular=0, roughness=1, fresnel=0),
    ))

    for name, vis, scale, r in [('Magnitude', True, 'Viridis', mag_range), ('Date', False, 'Jet', date_range), ('Depth', False, 'Viridis', dep_range)]:
        fig.add_trace(go.Scatter3d(
            x=[], y=[], z=[], mode='markers', hoverinfo='text',
            marker=dict(size=5, color=[], colorscale=scale, showscale=False, cmin=r[0], cmax=r[1], line=dict(width=1, color='rgba(50,50,50,0.8)'), opacity=0.8),
            name=f'Color: {name}', visible=vis
        ))

    if anim_mode == 'block' and len(unique_dates) > 0:
        d0 = datetime.strptime(unique_dates[0], '%Y-%m-%d')
        d_end = datetime.strptime(unique_dates[-1], '%Y-%m-%d')
        total_days = (d_end - d0).days
        num_blocks = (total_days // step_days) + 1
        frame_dates = [(d0 + timedelta(days=i*step_days)).strftime('%Y-%m-%d') for i in range(num_blocks)]
        
        new_counts = []
        old_counts = vpack.get('date_counts', [])
        date_map = {datetime.strptime(d_str, '%Y-%m-%d').date(): count for d_str, count in zip(unique_dates, old_counts)}
        for i in range(num_blocks):
            b_start = (d0 + timedelta(days=i*step_days)).date()
            b_end = b_start + timedelta(days=window_days)
            c = sum(count for d_obj, count in date_map.items() if b_start <= d_obj < b_end)
            new_counts.append(c)
        frame_counts = new_counts
    else:
        frame_dates = unique_dates
        frame_counts = vpack.get('date_counts', [])

    anim_data = {
        'lon': longitude, 'lat': latitude, 'dep': depth, 'mag': magnitude,
        'dnum': data.get('dates_num', []) if data else [], 'hover': vpack.get('hover', []),
        'unique_dates': unique_dates, 'date_to_cum': vpack.get('date_to_cum', {}),
        'anim_mode': anim_mode, 'window_days': window_days, 'step_days': step_days, 'mag_range': mag_range,
        'date_range': date_range, 'dep_range': dep_range, 'start_date': times[0][:10] if times else "",
        'date_counts': frame_counts, 'frame_dates': frame_dates, 'bbox': bbox, 'graph_bounds': data.get('graph_bounds') if data else None,
    }

    apply_3d_style(fig, [x_high[0], x_high[-1]], [y_high[-1], y_high[0]], [min_depth, 0])
    return fig, anim_data
