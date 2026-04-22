import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


# Import from our new core modules
from core.loader import load_csv
from core.geo_utils import build_map_mesh, MESH_HD_SIZE
from core.templates import generate_html, ANIMATION_BASE_DURATION_MS

N_CLUSTERS = 3

# ─── Visual Constants ──────────────────────────────────────────────────

COMMON_LAYOUT = dict(
    autosize=True,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=0, r=0, b=0, t=0),
    showlegend=False,
    uirevision=True
)

def apply_3d_style(fig: go.Figure, x_range: list[float], y_range: list[float], z_range: list[float]) -> None:
    """Unified style application for 3D scenes."""
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
            aspectratio=dict(x=1, y=1, z=0.5),
        )
    )

# ─── View Functions ──────────────────────────────────────────────────


def view_2d(longitude: list[float], latitude: list[float], magnitude: list[float], times: list[str], dates_num: list[float] | None = None, depth: list[float] | None = None, visual_pack: dict[str, Any] | None = None) -> go.Figure:
    """Generate a 2D map view with scatter and density traces."""
    # Use pre-calculated hover text
    all_hover = visual_pack.get('hover', []) if visual_pack else []

    fig = px.scatter_mapbox(
        lat=latitude, lon=longitude,
        size=magnitude,
        color=depth if depth is not None else magnitude,
        hover_name=all_hover,
        zoom=12,
        center=dict(
            lat=(min(latitude) + max(latitude)) / 2,
            lon=(min(longitude) + max(longitude)) / 2
        ),
        labels={"lat": "Latitude", "lon": "Longitude", "size": "Magnitude", "color": "Depth" if depth is not None else "Magnitude"},
    )


    
    # Trace 0: Scatter
    fig.update_traces(
        marker=dict(
            coloraxis=None,
            colorscale='Viridis',
            showscale=False,
        ),
        hoverinfo='text',
        hovertemplate='%{hovertext}<extra></extra>'
    )
    
    # Trace 1: Heatmap (Density)
    fig.add_trace(go.Densitymapbox(
        lat=latitude, lon=longitude, z=magnitude,
        radius=15, colorscale='Viridis',
        showscale=False, visible=False,
        name='Heatmap'
    ))
    
    if dates_num is not None:
        fig.data[0].customdata = np.array(dates_num).reshape(-1, 1)

    fig.update_layout(
        **COMMON_LAYOUT,
        mapbox_style="open-street-map"
    )
    return fig



def get_3d_static_figure(longitude: list[float], latitude: list[float], magnitude: list[float], depth: list[float], times: list[str], dates_num: list[float] | None = None, bbox: tuple[float, float, float, float] | None = None, visual_pack: dict[str, Any] | None = None, map_grids: tuple[Any, ...] | None = None) -> go.Figure:
    """Generate a high-quality 3D static view with pre-calculated hover and map mesh."""
    if bbox is None:
        bbox = (min(latitude), min(longitude), max(latitude), max(longitude))
    min_depth = min(depth)

    # 1. Map Mesh (Use provided grids or fallback)
    if map_grids:
        x_grid, y_grid, z_grid, surfacecolor, colorscale, _ = map_grids
    else:
        x_grid, y_grid, z_grid, surfacecolor, colorscale, _ = build_map_mesh(bbox, MESH_HD_SIZE)


    # 2. Points Hover (Pre-calculated)
    all_hover = visual_pack.get('hover', []) if visual_pack else []

    fig = go.Figure()

    # 0. Surface
    fig.add_trace(go.Surface(
        x=x_grid, y=y_grid, z=z_grid,
        surfacecolor=surfacecolor, colorscale=colorscale,
        showscale=False, opacity=0.9, hoverinfo='skip',
        lighting=dict(ambient=1, diffuse=0, specular=0, roughness=1, fresnel=0)

    ))

    # 1. Scatter Depth
    fig.add_trace(go.Scatter3d(
        x=longitude, y=latitude, z=depth,
        mode='markers', hovertext=all_hover,
        marker=dict(
            size=magnitude, sizemode='diameter', sizeref=0.12,
            color=depth, colorscale='Viridis',
            showscale=False,
            cmin=min(depth), cmax=max(depth),
            line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
            opacity=0.9,
        ),
        name='Earthquakes (Depth)', visible=True,
        showlegend=False,
        hovertemplate='%{hovertext}<extra></extra>'
    ))

    # 2. Scatter Date
    if dates_num is not None:
        fig.add_trace(go.Scatter3d(
            x=longitude, y=latitude, z=depth,
            mode='markers', hovertext=all_hover,
            marker=dict(
                size=magnitude, sizemode='diameter', sizeref=0.15,
                color=dates_num, colorscale='Jet',
                showscale=False,
                cmin=min(dates_num), cmax=max(dates_num),
                line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
                opacity=0.9,
            ),
            name='Earthquakes (Date)', visible=False,
            showlegend=False,
            hovertemplate='%{hovertext}<extra></extra>'
        ))
    else:
        fig.add_trace(go.Scatter3d(x=[], y=[], z=[], visible=False, hoverinfo='skip'))

    apply_3d_style(fig, [x_grid[0], x_grid[-1]], [y_grid[-1], y_grid[0]], [min_depth, 0])
    return fig



def get_3d_cluster_figure(longitude: list[float], latitude: list[float], magnitude: list[float], depth: list[float],
                            clustering_method: str = 'kmeans', clustering_params: dict[str, Any] | None = None,
                            bbox: tuple[float, float, float, float] | None = None, visual_pack: dict[str, Any] | None = None, map_grids: tuple[Any, ...] | None = None) -> tuple[go.Figure, np.ndarray, int]:
    """
    Generate the initial high-quality 3D Cluster figure.
    """
    min_depth = np.min(depth)
    if bbox is None:
        bbox = (np.min(latitude), np.min(longitude), np.max(latitude), np.max(longitude))

    # 1. Map Mesh (Use provided grids or fallback)
    if map_grids:
        x_grid, y_grid, z_grid, surfacecolor, colorscale, _ = map_grids
    else:
        x_grid, y_grid, z_grid, surfacecolor, colorscale, _ = build_map_mesh(bbox, MESH_HD_SIZE)

    # Note: Initial render uses full data (viz_mask=None)
    result = _generate_cluster_traces(
        longitude, latitude, magnitude, depth, 
        visual_pack.get('hover', []) if visual_pack else [],
        clustering_method, clustering_params,
        viz_mask=None
    )

    
    fig = go.Figure()

    # 0. Surface (Map)
    fig.add_trace(go.Surface(
        x=x_grid, y=y_grid, z=z_grid,
        surfacecolor=surfacecolor, colorscale=colorscale,
        showscale=False, opacity=0.9, hoverinfo='skip',
        lighting=dict(ambient=1, diffuse=0, specular=0, roughness=1, fresnel=0)
    ))

    # Add all generated cluster layers (Wireframes, Solids, Scatter, Centroids, Proxies)
    for t in result['traces']:
        fig.add_trace(t)

    apply_3d_style(fig, [x_grid[0], x_grid[-1]], [y_grid[-1], y_grid[0]], [min_depth, 0])
    return fig, result['labels'], result['n_clusters']


def get_cluster_update_traces(longitude: list[float], latitude: list[float], magnitude: list[float], depth: list[float], hover: list[str],
                              clustering_method: str = 'kmeans', clustering_params: dict[str, Any] | None = None, viz_mask: np.ndarray | None = None) -> dict[str, Any]:
    """
    Perform clustering and return a JSON-ready package for async updates.
    """
    result = _generate_cluster_traces(
        longitude, latitude, magnitude, depth, hover,
        clustering_method, clustering_params, viz_mask=viz_mask
    )

    
    # Convert Plotly objects to JSON-serializable dictionaries
    json_traces = [t.to_plotly_json() for t in result['traces']]
    
    return {
        'traces': json_traces,
        'labels': result['labels'].tolist(),
        'n_clusters': result['n_clusters']
    }


def _generate_cluster_traces(longitude: list[float] | np.ndarray, latitude: list[float] | np.ndarray, magnitude: list[float] | np.ndarray, depth: list[float] | np.ndarray, hover: list[str],
                             method: str = 'kmeans', params: dict[str, Any] | None = None, viz_mask: np.ndarray | None = None) -> dict[str, Any]:
    """
    Shared helper to perform clustering and generate Plotly trace objects.
    Ensures identical logic between initial render and async updates.
    """
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import MiniBatchKMeans, DBSCAN
    from scipy.spatial import ConvexHull

    params = params or {}
    longitude, latitude, depth = np.array(longitude), np.array(latitude), np.array(depth)
    magnitude = np.array(magnitude)
    X_orig = np.column_stack((longitude, latitude, depth))
    
    # --- 1. CLUSTERING EXECUTION ---
    # Runs on ALL points provided (which should be filtered by Date only)
    if method == 'dbscan':
        eps_m = float(params.get('dbscan_eps', 500))
        min_samples = int(params.get('dbscan_min_samples', 5))
        
        # DBSCAN needs meters for EPS to make sense
        avg_lat = np.mean(latitude)
        X_meters = np.zeros_like(X_orig)
        X_meters[:, 0] = longitude * 111320 * np.cos(np.radians(avg_lat))
        X_meters[:, 1] = latitude * 111320
        X_meters[:, 2] = depth * 1000
        
        db = DBSCAN(eps=eps_m, min_samples=min_samples).fit(X_meters)
        labels = db.labels_
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        if n_clusters == 0:
            n_clusters = 1
            labels = np.zeros(len(X_orig), dtype=int)
    else:
        n_clusters_req = int(params.get('kmeans_clusters', 3))
        if len(X_orig) >= n_clusters_req:
            X_scaled = StandardScaler().fit_transform(X_orig)
            kmeans = MiniBatchKMeans(n_clusters=n_clusters_req, random_state=42, n_init='auto').fit(X_scaled)
            labels = kmeans.labels_
            n_clusters = n_clusters_req
            centroids_scaled = kmeans.cluster_centers_
        else:
            labels = np.zeros(len(X_orig), dtype=int)
            n_clusters = 1

    # --- 2. OUTLIER FILTERING ---
    # Optional: filter out points too far from their centroid for cleaner hull generation
    # Also based on the full cluster set
    display_labels = labels.copy()
    if method == 'kmeans' and float(params.get('kmeans_max_dist', 0)) > 0:
        max_d = float(params.get('kmeans_max_dist', 0))
        for i in range(n_clusters):
            idx = (labels == i)
            if not np.any(idx): continue
            pts_c = X_orig[idx]
            center = np.mean(pts_c, axis=0)
            dists = np.sqrt(((pts_c[:,1]-center[1])*111320)**2 + 
                            ((pts_c[:,0]-center[0])*111320*np.cos(np.radians(center[1])))**2 + 
                            ((pts_c[:,2]-center[2])*1000)**2)
            display_labels[np.where(idx)[0][dists > max_d]] = -1

    # --- 3. TRACE GENERATION ---
    cluster_colors = px.colors.qualitative.Plotly
    traces = []

    # A. Wireframe Hulls (Based on full cluster groups)
    for i in range(n_clusters):
        pts = X_orig[display_labels == i]
        if len(pts) > 4:
            try:
                hull = ConvexHull(pts)
                lx, ly, lz = [], [], []
                for s in hull.simplices:
                    for c in [(0,1),(1,2),(2,0)]:
                        lx.extend([pts[s[c[0]],0], pts[s[c[1]],0], None])
                        ly.extend([pts[s[c[0]],1], pts[s[c[1]],1], None])
                        lz.extend([pts[s[c[0]],2], pts[s[c[1]],2], None])
                traces.append(go.Scatter3d(
                    x=lx, y=ly, z=lz, mode='lines',
                    line=dict(color=cluster_colors[i % len(cluster_colors)], width=2),
                    opacity=0.4, name=f'Cluster {i+1} Wire', visible=True, showlegend=False, hoverinfo='skip'
                ))
            except: traces.append(go.Scatter3d(x=[], y=[], z=[], visible=False, hoverinfo='skip'))
        else: traces.append(go.Scatter3d(x=[], y=[], z=[], visible=False, hoverinfo='skip'))

    # B. Solid Volumes (Based on full cluster groups)
    for i in range(n_clusters):
        pts = X_orig[display_labels == i]
        if len(pts) > 4:
            try:
                traces.append(go.Mesh3d(
                    x=pts[:,0].tolist(), y=pts[:,1].tolist(), z=pts[:,2].tolist(), 
                    color=cluster_colors[i % len(cluster_colors)], opacity=0.15, alphahull=0, 
                    name=f'Cluster {i+1} Solid', visible=False, showlegend=False, hoverinfo='skip'
                ))
            except: traces.append(go.Mesh3d(x=[], y=[], z=[], visible=False, hoverinfo='skip'))
        else: traces.append(go.Mesh3d(x=[], y=[], z=[], visible=False, hoverinfo='skip'))

    # C. Earthquake Markers (Optionally filtered for "Visualization Only" Mag/Dep ranges)
    if viz_mask is not None:
        v_idx = viz_mask
        v_lon = longitude[v_idx]
        v_lat = latitude[v_idx]
        v_dep = depth[v_idx]
        v_mag = magnitude[v_idx]
        v_labels = display_labels[v_idx]
        v_hover = [hover[i] for i, m in enumerate(v_idx) if m]
    else:
        v_lon, v_lat, v_dep, v_mag, v_labels, v_hover = longitude, latitude, depth, magnitude, display_labels, hover

    pt_colors = [cluster_colors[int(l) % len(cluster_colors)] if l >= 0 else '#888888' for l in v_labels]
    
    traces.append(go.Scatter3d(
        x=v_lon.tolist(), y=v_lat.tolist(), z=v_dep.tolist(), mode='markers', hovertext=v_hover,
        marker=dict(size=v_mag.tolist(), sizemode='diameter', sizeref=0.12, color=pt_colors, line=dict(width=1, color='rgba(50,50,50,0.8)'), opacity=0.9),
        name='Earthquakes', visible=True, showlegend=False, hovertemplate='%{hovertext}<extra></extra>'
    ))


    # D. Centroids (2N+2)
    if method == 'kmeans':
        cx, cy, cz, ch = [], [], [], []
        for i in range(n_clusters):
            idx_c = labels == i
            if np.any(idx_c):
                m = np.mean(X_orig[idx_c], axis=0); am = np.mean(magnitude[idx_c])
                cx.append(m[0]); cy.append(m[1]); cz.append(m[2])
                ch.append(f"<b>Cluster {i+1} Centroid</b><br>Lat: {m[1]:.4f}<br>Lon: {m[0]:.4f}<br>Dep: {abs(m[2]):.2f}km<br>Avg Mag: {am:.2f}")
        traces.append(go.Scatter3d(
            x=cx, y=cy, z=cz, mode='markers', hovertext=ch,
            marker=dict(symbol='diamond', size=8, color='#ffffff', line=dict(width=2, color='#000')),
            name='Cluster Centroids', showlegend=True, visible=True, hovertemplate='%{hovertext}<extra></extra>'
        ))
    else: traces.append(go.Scatter3d(x=[], y=[], z=[], visible=False, showlegend=False))

    # E. Legend Proxies (2N+3..3N+2)
    for i in range(n_clusters):
        vis = bool(np.any(display_labels == i))
        traces.append(go.Scatter3d(
            x=[None], y=[None], z=[None], mode='markers',
            marker=dict(color=cluster_colors[i % len(cluster_colors)], size=10),
            name=f'Cluster {i+1}', visible=vis, showlegend=vis
        ))

    return {'traces': traces, 'labels': labels, 'n_clusters': n_clusters}





def get_3d_animated_figure(longitude: list[float], latitude: list[float], magnitude: list[float], depth: list[float], times: list[str],
                           on_progress: Callable[[str], None] | None = None, anim_mode: str = 'accumulation', window_days: int = 5, data: dict[str, Any] | None = None, bbox: tuple[float, float, float, float] | None = None, map_grids: tuple[Any, ...] | None = None) -> tuple[go.Figure, dict[str, Any]]:
    """Generate a 3D figure for animation with timeline interaction."""
    def _report(msg):
        logger.info(msg)
        if on_progress: on_progress(msg)

    _report("Preparing 3D animation data...")
    vpack = data.get('visual_pack', {})
    unique_dates = vpack.get('unique_dates', [])

    if bbox is None:
        bbox = (min(latitude), min(longitude), max(latitude), max(longitude))
    min_depth = min(depth)

    # 1. Map Mesh (Use provided grids or fallback)
    if map_grids:
        x_high, y_high, z_high, mat_high, scale_high, map_data = map_grids
    else:
        _report("Building map mesh (HD)...")
        x_high, y_high, z_high, mat_high, scale_high, map_data = build_map_mesh(bbox, MESH_HD_SIZE)

    mag_range = vpack.get('mag_range', [0, 10])
    date_range = vpack.get('date_range', [0, 0])
    dep_range = vpack.get('dep_range', [0, 0])

    fig = go.Figure()

    # 0. Surface HD
    fig.add_trace(go.Surface(
        x=x_high, y=y_high, z=z_high,
        surfacecolor=mat_high, colorscale=scale_high,
        showscale=False, opacity=0.85, hoverinfo='skip', visible=True,
        lighting=dict(ambient=1, diffuse=0, specular=0, roughness=1, fresnel=0),
    ))

    
    # 1. Scatter Mag (Trace 1)
    fig.add_trace(go.Scatter3d(
        x=[], y=[], z=[],
        mode='markers', hoverinfo='text',
        marker=dict(
            size=[], sizemode='diameter', sizeref=0.1,
            color=[], colorscale='Viridis',
            showscale=False, cmin=mag_range[0], cmax=mag_range[1],
            line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
            opacity=0.8,
        ),
        name='Color: Magnitude', visible=True,
    ))
    
    # 2. Scatter Date (Trace 2)
    fig.add_trace(go.Scatter3d(
        x=[], y=[], z=[],
        mode='markers', hoverinfo='text',
        marker=dict(
            size=[], sizemode='diameter', sizeref=0.1,
            color=[], colorscale='Jet',
            showscale=False, cmin=date_range[0], cmax=date_range[1],
            line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
            opacity=0.8,
        ),
        name='Color: Date', visible=False,
    ))

    # 3. Scatter Depth (Trace 3)
    fig.add_trace(go.Scatter3d(
        x=[], y=[], z=[],
        mode='markers', hoverinfo='text',
        marker=dict(
            size=[], sizemode='diameter', sizeref=0.1,
            color=[], colorscale='Viridis',
            showscale=False, cmin=dep_range[0], cmax=dep_range[1],
            line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
            opacity=0.8,
        ),
        name='Color: Depth', visible=False,
    ))

    _report("Packaging animation data...")
    anim_data = {
        'lon': longitude,
        'lat': latitude,
        'dep': depth,
        'mag': magnitude,
        'dnum': data.get('dates_num', []),
        'hover': vpack.get('hover', []),
        'unique_dates': unique_dates,
        'date_to_cum': vpack.get('date_to_cum', {}),
        'anim_mode': anim_mode,
        'window_days': window_days,
        'mag_range': mag_range,
        'date_range': date_range,
        'dep_range': dep_range,
        'start_date': times[0][:10],
        'date_counts': vpack.get('date_counts', []),
    }

    apply_3d_style(fig, [x_high[0], x_high[-1]], [y_high[-1], y_high[0]], [min_depth, 0])
    return fig, anim_data



def build_view_html(data: dict[str, Any], view_style: int, back_button: bool = True, on_progress: Callable[[str], None] | None = None,
                    anim_mode: str = 'accumulation', window_days: int = 5, clustering_method: str = 'kmeans',
                    clustering_params: dict[str, Any] | None = None) -> tuple[str, bool]:
    """Orchestrate view generation and return final HTML."""
    def _report(msg):
        if on_progress: on_progress(msg)

    lon, lat, mag, dep, times = data['longitude'], data['latitude'], data['magnitude'], data['depth'], data['times']
    d_num = data.get('dates_num', [])
    vpack = data.get('visual_pack', {})

    is_fallback = False
    
    # 1. Bounding Box Consistency
    bbox = data.get('bbox')
    if bbox is None:
        bbox = (min(lat), min(lon), max(lat), max(lon))
        data['bbox'] = bbox

    # 2. Shared Map Mesh (HD)
    map_grids = None
    if view_style in [1, 2, 3]:
        _report("Preparing map mesh…")
        map_grids = build_map_mesh(bbox, MESH_HD_SIZE)
        is_fallback = (map_grids[5] is None) # index 5 is map_data

    # 3. View Routing
    if view_style == 0:
        _report("Generating 2D map…")
        import socket
        try:
            socket.create_connection(("a.tile.openstreetmap.org", 80), timeout=1.0)
            is_fallback = False
        except Exception:
            is_fallback = True

        fig = view_2d(lon, lat, mag, times, dates_num=d_num, depth=dep, visual_pack=vpack)
        static_data = data.copy()
        static_data['hover'] = vpack.get('hover', [])
        static_data['mag_limit'] = vpack.get('mag_range', [0, 10])
        static_data['date_limit'] = vpack.get('date_range', [0, 0])
        static_data['dep_limit'] = vpack.get('dep_range', [0, 0])
        static_data['start_date'] = times[0][:10] if times else ""
        html = generate_html(fig, back_button=back_button, earthquake_data=static_data, is_fallback=is_fallback)

    elif view_style == 1:
        _report("Rendering 3D static view…")
        fig = get_3d_static_figure(lon, lat, mag, dep, times, dates_num=d_num, bbox=bbox, visual_pack=vpack, map_grids=map_grids)
        static_data = data.copy()
        static_data['hover'] = vpack.get('hover', [])
        static_data['mag_limit'] = vpack.get('mag_range', [0, 10])
        static_data['date_limit'] = vpack.get('date_range', [0, 0])
        static_data['dep_limit'] = vpack.get('dep_range', [0, 0])
        static_data['start_date'] = times[0][:10] if times else ""
        html = generate_html(fig, is_3d=True, back_button=back_button, earthquake_data=static_data, is_fallback=is_fallback)

    elif view_style == 2:
        fig, anim_data = get_3d_animated_figure(lon, lat, mag, dep, times, 
                                               on_progress=on_progress, anim_mode=anim_mode, 
                                               window_days=window_days, data=data, bbox=bbox, map_grids=map_grids)
        html = generate_html(fig, is_animated=True, is_3d=True, back_button=back_button, earthquake_data=anim_data, is_fallback=is_fallback)

    elif view_style == 3:
        fig, labels, n_clusters = get_3d_cluster_figure(
            lon, lat, mag, dep, 
            clustering_method=clustering_method,
            clustering_params=clustering_params,
            bbox=bbox,
            visual_pack=vpack,
            map_grids=map_grids
        )

        cluster_data = data.copy()
        cluster_data['cluster'] = labels.tolist()
        cluster_data['hover'] = vpack.get('hover', [])
        cluster_data['mag_limit'] = vpack.get('mag_range', [0, 10])
        cluster_data['date_limit'] = vpack.get('date_range', [0, 0])
        cluster_data['dep_limit'] = vpack.get('dep_range', [0, 0])
        cluster_data['n_clusters'] = n_clusters
        cluster_data['clustering_method'] = clustering_method
        cluster_data['clustering_params'] = clustering_params
        cluster_data['start_date'] = times[0][:10] if times else ""
        html = generate_html(fig, is_cluster=True, is_3d=True, back_button=back_button, earthquake_data=cluster_data, is_fallback=is_fallback)


    else:
        raise ValueError(f"Invalid view style: {view_style}")

    return html, is_fallback