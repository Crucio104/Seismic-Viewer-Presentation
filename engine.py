from datetime import datetime

# Import from our new core modules
from core.loader import load_csv
from core.geo_utils import build_map_mesh, MESH_HD_SIZE, MESH_LOW_SIZE
from core.templates import generate_html, _make_hover, ANIMATION_BASE_DURATION_MS

# ─── View Functions ──────────────────────────────────────────────────

N_CLUSTERS = 3

def view_2d(longitude, latitude, magnitude, times, dates_num=None, depth=None):
    import plotly.express as px
    import plotly.graph_objects as go
    import pandas as pd
    import numpy as np
    
    # Create hover text using the helper
    hover_df = pd.DataFrame({
        'lon': longitude, 'lat': latitude,
        'mag': magnitude, 'dep': depth if depth is not None else [0]*len(longitude), 
        'time_str': times
    })
    all_hover = _make_hover(hover_df)

    fig = px.scatter_mapbox(
        lat=latitude, lon=longitude,
        size=magnitude,
        color=depth if depth is not None else magnitude,
        hover_name=all_hover,
        zoom=12,
        labels={"lat": "Latitude", "lon": "Longitude", "size": "Magnitude", "color": "Depth" if depth is not None else "Magnitude"},
    )
    
    # Trace 0: Scatter
    fig.update_traces(
        marker=dict(
            coloraxis=None,
            colorscale='Viridis',
            showscale=False,
            colorbar=dict(
                title=dict(text="Depth" if depth is not None else "Magnitude", side='top', font=dict(color='#fff')),
                x=0.98, xanchor='right', y=0.5,
                thickness=12, len=0.35,
                bgcolor='rgba(45, 45, 65, 0.6)',
                bordercolor='rgba(255, 255, 255, 0.25)',
                borderwidth=1,
                tickfont=dict(color='#fff'),
            )
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
        autosize=True,
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig


def get_3d_static_figure(longitude, latitude, magnitude, depth, times, dates_num=None):
    import pandas as pd
    import plotly.graph_objects as go
    import numpy as np
    min_lon, max_lon = min(longitude), max(longitude)
    min_lat, max_lat = min(latitude), max(latitude)
    min_depth = min(depth)
    bbox = (min_lat, min_lon, max_lat, max_lon)

    print("Preparing 3D static view...")
    x_grid, y_grid, z_grid, surfacecolor, colorscale, _ = build_map_mesh(
        bbox, MESH_HD_SIZE
    )

    hover_df = pd.DataFrame({
        'lon': longitude, 'lat': latitude,
        'mag': magnitude, 'dep': depth,
        'time_str': times
    })
    all_hover = _make_hover(hover_df)

    fig = go.Figure()

    # 0. Surface (Index 0)
    fig.add_trace(go.Surface(
        x=x_grid, y=y_grid, z=z_grid,
        surfacecolor=surfacecolor, colorscale=colorscale,
        showscale=False, opacity=0.9, hoverinfo='skip'
    ))

    # 1. Scatter Depth (Index 1)
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

    # 2. Scatter Date (Index 2)
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

    fig.update_layout(
        autosize=True,
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        scene=dict(
            bgcolor='#f8f8fc',
            xaxis=dict(title='Longitude', range=[x_grid[0], x_grid[-1]], showspikes=False),
            yaxis=dict(title='Latitude', range=[y_grid[-1], y_grid[0]], showspikes=False),
            zaxis=dict(title='Depth (km)', range=[min_depth, 0], showspikes=False),
            aspectmode='manual',
            aspectratio=dict(x=1, y=1, z=0.5),
        ),
        margin=dict(l=0, r=0, b=0, t=0),
    )
    return fig


def get_3d_cluster_figure(longitude, latitude, magnitude, depth, times,
                          dates_num=None, clustering_method='kmeans', clustering_params=None):
    """Generate a 3D figure dedicated to cluster analysis.

    Trace layout:
        0        : Surface map
        1..N     : Wireframe hulls  (one per cluster)
        N+1..2N  : Solid volumes    (one per cluster)
        2N+1     : Scatter points (colored by cluster)
        2N+2..3N+1: Legend proxies
    """
    import pandas as pd
    import plotly.graph_objects as go
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from scipy.spatial import ConvexHull
    import plotly.express as px

    magnitude = np.array(magnitude)
    longitude = np.array(longitude)
    latitude = np.array(latitude)
    depth = np.array(depth)
    
    min_depth = np.min(depth)
    bbox = (np.min(latitude), np.min(longitude), np.max(latitude), np.max(longitude))

    print(f"Preparing 3D cluster view ({clustering_method})...")
    x_grid, y_grid, z_grid, surfacecolor, colorscale, _ = build_map_mesh(
        bbox, MESH_HD_SIZE
    )

    hover_df = pd.DataFrame({
        'lon': longitude, 'lat': latitude,
        'mag': magnitude, 'dep': depth,
        'time_str': times
    })
    all_hover = _make_hover(hover_df)

    # ── Clustering ──────────────────────────────────────────────────
    X_orig = np.column_stack((longitude, latitude, depth))
    X_scaled = StandardScaler().fit_transform(X_orig)

    params = clustering_params or {}
    centroids = None

    if clustering_method == 'dbscan':
        from sklearn.cluster import DBSCAN
        eps_m = float(params.get('dbscan_eps', 500))
        min_samples = int(params.get('dbscan_min_samples', 5))
        
        # Project to local metric space (meters) for DBSCAN
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
    else:  # kmeans
        from sklearn.cluster import MiniBatchKMeans
        n_clusters_req = int(params.get('kmeans_clusters', N_CLUSTERS))
        if len(X_orig) >= n_clusters_req:
            kmeans = MiniBatchKMeans(
                n_clusters=n_clusters_req, random_state=42,
                n_init='auto', batch_size=1024
            ).fit(X_scaled)
            labels = kmeans.labels_
            n_clusters = n_clusters_req
            centroids = kmeans.cluster_centers_
        else:
            labels = np.zeros(len(X_orig), dtype=int)
            n_clusters = 1

    cluster_colors = px.colors.qualitative.Plotly
    fig = go.Figure()

    # Create a copy of labels for visual display (filtering by distance)
    display_labels = labels.copy()
    if clustering_method == 'kmeans' and float(params.get('kmeans_max_dist', 0)) > 0 and centroids is not None:
        kmeans_dist = float(params.get('kmeans_max_dist', 0))
        for i in range(n_clusters):
            idx = labels == i
            if not np.any(idx): continue
            
            pts_cluster = X_orig[idx]
            # Use physical centroid calculated from original points in the cluster
            c_phys = np.mean(pts_cluster, axis=0)
            
            d_lat = (pts_cluster[:, 1] - c_phys[1]) * 111320
            d_lon = (pts_cluster[:, 0] - c_phys[0]) * 111320 * np.cos(np.radians(c_phys[1]))
            d_dep = (pts_cluster[:, 2] - c_phys[2]) * 1000
            dists_m = np.sqrt(d_lat**2 + d_lon**2 + d_dep**2)
            
            # Find points in this cluster that are too far
            far_mask = dists_m > kmeans_dist
            # Indices relative to X_orig
            cluster_indices = np.where(idx)[0]
            display_labels[cluster_indices[far_mask]] = -1

    # 0. Surface
    fig.add_trace(go.Surface(
        x=x_grid, y=y_grid, z=z_grid,
        surfacecolor=surfacecolor, colorscale=colorscale,
        showscale=False, opacity=0.9, hoverinfo='skip'
    ))

    # 1..N  Wireframe hulls
    kmeans_dist = float(params.get('kmeans_max_dist', 0)) if clustering_method == 'kmeans' else 0

    for i in range(n_clusters):
        idx = display_labels == i
        pts = X_orig[idx]

        if len(pts) > 4:
            try:
                hull = ConvexHull(pts)
                lx, ly, lz = [], [], []
                for s in hull.simplices:
                    for c in [(0,1),(1,2),(2,0)]:
                        lx.extend([pts[s[c[0]],0], pts[s[c[1]],0], None])
                        ly.extend([pts[s[c[0]],1], pts[s[c[1]],1], None])
                        lz.extend([pts[s[c[0]],2], pts[s[c[1]],2], None])
                fig.add_trace(go.Scatter3d(
                    x=lx, y=ly, z=lz, mode='lines',
                    line=dict(color=cluster_colors[i % len(cluster_colors)], width=2),
                    opacity=0.4, name=f'Cluster {i+1} Wire',
                    visible=True, showlegend=False, hoverinfo='skip'
                ))
            except Exception:
                fig.add_trace(go.Scatter3d(x=[], y=[], z=[], visible=False, hoverinfo='skip'))
        else:
            fig.add_trace(go.Scatter3d(x=[], y=[], z=[], visible=False, hoverinfo='skip'))

    # N+1..2N  Solid volumes
    for i in range(n_clusters):
        idx = display_labels == i
        pts = X_orig[idx]

        if len(pts) > 4:
            try:
                fig.add_trace(go.Mesh3d(
                    x=pts[:,0], y=pts[:,1], z=pts[:,2],
                    color=cluster_colors[i % len(cluster_colors)],
                    opacity=0.15, alphahull=0,
                    name=f'Cluster {i+1} Solid',
                    visible=False, showlegend=False,
                    hoverinfo='skip', hovertemplate=None
                ))
            except Exception:
                fig.add_trace(go.Mesh3d(x=[], y=[], z=[], visible=False, hoverinfo='skip', showlegend=False))
        else:
            fig.add_trace(go.Mesh3d(x=[], y=[], z=[], visible=False, hoverinfo='skip', showlegend=False))

    # 2N+1  Scatter points colored by cluster
    color_map = [cluster_colors[int(l) % len(cluster_colors)] if l >= 0 else '#888888' for l in display_labels]
    fig.add_trace(go.Scatter3d(
        x=longitude, y=latitude, z=depth,
        mode='markers', hovertext=all_hover,
        marker=dict(
            size=magnitude, sizemode='diameter', sizeref=0.12,
            color=color_map,
            line=dict(width=1, color='rgba(50,50,50,0.8)'),
            opacity=0.9,
        ),
        name='Earthquakes', visible=True,
        showlegend=False,
        hovertemplate='%{hovertext}<extra></extra>'
    ))

    # 2N+2 Centroids (K-Means only)
    if clustering_method == 'kmeans':
        cx, cy, cz, chover = [], [], [], []
        for i in range(n_clusters):
            idx_c = labels == i
            pts_c = X_orig[idx_c]
            if len(pts_c) > 0:
                m = np.mean(pts_c, axis=0)
                avg_mag = np.mean(magnitude[idx_c])
                cx.append(m[0]); cy.append(m[1]); cz.append(m[2])
                chover.append(
                    f"<b>Cluster {i+1} Centroid</b><br>"
                    f"Latitude: {m[1]:.4f}<br>"
                    f"Longitude: {m[0]:.4f}<br>"
                    f"Depth: {abs(m[2]):.2f} km<br>"
                    f"Avg Magnitude: {avg_mag:.2f}"
                )
            else:
                cx.append(None); cy.append(None); cz.append(None); chover.append("")
        fig.add_trace(go.Scatter3d(
            x=cx, y=cy, z=cz, mode='markers',
            hovertext=chover,
            marker=dict(symbol='diamond', size=8, color='#ffffff', line=dict(width=2, color='#000')),
            name='Cluster Centroids', showlegend=True, visible=True, 
            hoverinfo='text', hovertemplate='%{hovertext}<extra></extra>'
        ))
    else:
        # Dummy trace to maintain index parity for legend proxies if needed
        fig.add_trace(go.Scatter3d(x=[], y=[], z=[], visible=False, showlegend=False))

    # 2N+2..3N+1  Legend proxies
    for i in range(n_clusters):
        # We check if any point is actually assigned to this cluster after distance filtering
        # to ensure the legend is consistent
        is_visible = bool(np.any(display_labels == i))
        fig.add_trace(go.Scatter3d(
            x=[None], y=[None], z=[None], mode='markers',
            marker=dict(color=cluster_colors[i % len(cluster_colors)], size=10),
            name=f'Cluster {i+1}', visible=is_visible, showlegend=is_visible
        ))

    fig.update_layout(
        autosize=True,
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        legend=dict(font=dict(color='#fff'), bgcolor='rgba(0,0,0,0)'),
        scene=dict(
            bgcolor='#f8f8fc',
            xaxis=dict(title='Longitude', range=[x_grid[0], x_grid[-1]], showspikes=False),
            yaxis=dict(title='Latitude', range=[y_grid[-1], y_grid[0]], showspikes=False),
            zaxis=dict(title='Depth (km)', range=[min_depth, 0], showspikes=False),
            aspectmode='manual',
            aspectratio=dict(x=1, y=1, z=0.5),
        ),
        margin=dict(l=0, r=0, b=0, t=0),
    )
    return fig, display_labels, n_clusters


def get_3d_animated_figure(longitude, latitude, magnitude, depth, times,
                           on_progress=None, anim_mode='accumulation', window_days=5, data=None):
    import pandas as pd
    import plotly.graph_objects as go
    import numpy as np
    import PIL.Image
    def _report(msg):
        print(msg)
        if on_progress:
            on_progress(msg)

    _report("Preparing 3D animation data...")
    # Dates are already parsed as dates_num in loader.py
    df = pd.DataFrame({
        'lon': longitude, 'lat': latitude,
        'mag': magnitude, 'dep': depth, 'time_str': times,
        'date_num': [float(d) for d in data['dates_num']] if 'dates_num' in data else []
    })
    
    # We still need date strings for grouping, but we can get them from times list efficiently
    df['date'] = [t[:10] for t in times]
    unique_dates = sorted(df['date'].unique())

    bbox = (min(latitude), min(longitude), max(latitude), max(longitude))
    min_depth = min(depth)


    _report("Building map mesh (HD)...")
    x_high, y_high, z_high, mat_high, scale_high, map_data = build_map_mesh(
        bbox, MESH_HD_SIZE
    )

    mag_min, mag_max = df['mag'].min(), df['mag'].max()
    date_n_min, date_n_max = df['date_num'].min(), df['date_num'].max()
    dep_min, dep_max = df['dep'].min(), df['dep'].max()

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
            showscale=False, cmin=mag_min, cmax=mag_max,
            colorbar=dict(
                title=dict(text="Magnitude", side='top', font=dict(color='#fff')),
                x=0.98, xanchor='right', y=0.5, thickness=15, len=0.4,
                bgcolor='rgba(45, 45, 65, 0.6)',
                bordercolor='rgba(255, 255, 255, 0.25)',
                borderwidth=1,
                tickfont=dict(color='#fff'),
            ),
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
            showscale=False, cmin=date_n_min, cmax=date_n_max,
            colorbar=dict(
                title=dict(text="Date", side='top', font=dict(color='#fff')),
                x=0.98, xanchor='right', y=0.5, thickness=15, len=0.4,
                bgcolor='rgba(45, 45, 65, 0.6)',
                bordercolor='rgba(255, 255, 255, 0.25)',
                borderwidth=1,
                tickfont=dict(color='#fff'),
            ),
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
            showscale=False, cmin=dep_min, cmax=dep_max,
            colorbar=dict(
                title=dict(text="Depth", side='top', font=dict(color='#fff')),
                x=0.98, xanchor='right', y=0.5, thickness=15, len=0.4,
                bgcolor='rgba(45, 45, 65, 0.6)',
                bordercolor='rgba(255, 255, 255, 0.25)',
                borderwidth=1,
                tickfont=dict(color='#fff'),
            ),
            line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
            opacity=0.8,
        ),
        name='Color: Depth', visible=False,
    ))

    _report("Packaging animation data...")
    all_hover = _make_hover(df)
    
    # Pre-calculate cumulative indices for all dates
    date_counts = df.groupby('date').size()
    cum = 0
    date_to_cum = {}
    for d in unique_dates:
        cum += int(date_counts[d])
        date_to_cum[d] = cum

    anim_data = {
        'lon': df['lon'].tolist(),
        'lat': df['lat'].tolist(),
        'dep': df['dep'].tolist(),
        'mag': df['mag'].tolist(),
        'dnum': df['date_num'].tolist(),
        'hover': all_hover,
        'unique_dates': unique_dates,
        'date_to_cum': date_to_cum,
        'anim_mode': anim_mode,
        'window_days': window_days,
        'mag_range': [float(mag_min), float(mag_max)],
        'date_range': [float(date_n_min), float(date_n_max)],
        'dep_range': [float(dep_min), float(dep_max)],
        'start_date': times[0][:10],

    }

    fig.update_layout(
        autosize=True,
        paper_bgcolor='rgba(0,0,0,0)',
        scene=dict(
            bgcolor='#f8f8fc',
            xaxis=dict(title='Longitude', range=[x_high[0], x_high[-1]], showspikes=False),
            yaxis=dict(title='Latitude', range=[y_high[-1], y_high[0]], showspikes=False),
            zaxis=dict(title='Depth (km)', range=[min_depth, 0], showspikes=False),
            aspectmode='manual', aspectratio=dict(x=1, y=1, z=0.5),
        ),
        margin=dict(l=0, r=0, b=0, t=0),
    )
    return fig, anim_data


def build_view_html(data, view_style, back_button=True, on_progress=None,
                    anim_mode='accumulation', window_days=5, clustering_method='kmeans',
                    clustering_params=None):
    import pandas as pd
    def _report(msg):
        if on_progress: on_progress(msg)

    lon, lat, mag, dep, times = data['longitude'], data['latitude'], data['magnitude'], data['depth'], data['times']
    d_num = data.get('dates_num', [])

    if view_style == 0:
        _report("Generating 2D map…")
        fig = view_2d(lon, lat, mag, times, dates_num=d_num, depth=dep)
        static_data = data.copy()
        static_data['hover'] = _make_hover(pd.DataFrame({'lon': lon, 'lat': lat, 'mag': mag, 'dep': dep, 'time_str': times}))
        static_data['mag_limit'] = [min(mag), max(mag)]
        static_data['date_limit'] = [min(d_num), max(d_num)] if d_num else [0, 0]
        static_data['dep_limit'] = [min(dep), max(dep)]
        static_data['start_date'] = times[0][:10]
        return generate_html(fig, back_button=back_button, earthquake_data=static_data)
    elif view_style == 1:
        _report("Preparing 3D static view…")
        fig = get_3d_static_figure(lon, lat, mag, dep, times, dates_num=d_num)
        static_data = data.copy()
        static_data['hover'] = _make_hover(pd.DataFrame({'lon': lon, 'lat': lat, 'mag': mag, 'dep': dep, 'time_str': times}))
        static_data['mag_limit'] = [min(mag), max(mag)]
        static_data['date_limit'] = [min(d_num), max(d_num)] if d_num else [0, 0]
        static_data['dep_limit'] = [min(dep), max(dep)]
        static_data['start_date'] = times[0][:10]
        return generate_html(fig, back_button=back_button, earthquake_data=static_data)
    elif view_style == 2:
        fig, anim_data = get_3d_animated_figure(lon, lat, mag, dep, times, 
                                               on_progress=on_progress, anim_mode=anim_mode, 
                                               window_days=window_days, data=data)
        return generate_html(fig, is_animated=True, back_button=back_button, earthquake_data=anim_data)
    elif view_style == 3:
        _report("Preparing cluster analysis…")
        fig, labels, n_clusters = get_3d_cluster_figure(
            lon, lat, mag, dep, times, dates_num=d_num,
            clustering_method=clustering_method,
            clustering_params=clustering_params
        )
        cluster_data = data.copy()
        cluster_data['cluster'] = labels.tolist()
        cluster_data['hover'] = _make_hover(pd.DataFrame({'lon': lon, 'lat': lat, 'mag': mag, 'dep': dep, 'time_str': times}))
        cluster_data['mag_limit'] = [min(mag), max(mag)]
        cluster_data['date_limit'] = [min(d_num), max(d_num)] if d_num else [0, 0]
        cluster_data['dep_limit'] = [min(dep), max(dep)]
        cluster_data['n_clusters'] = n_clusters
        cluster_data['clustering_method'] = clustering_method
        cluster_data['clustering_params'] = clustering_params
        cluster_data['start_date'] = times[0][:10]
        return generate_html(fig, is_cluster=True, back_button=back_button, earthquake_data=cluster_data)

    else:
        raise ValueError(f"Invalid view style: {view_style}")