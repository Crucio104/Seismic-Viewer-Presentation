import plotly.graph_objects as go
import numpy as np
import pandas as pd
import PIL.Image
from datetime import datetime

# Import from our new core modules
from core.loader import load_csv
from core.geo_utils import build_map_mesh, MESH_HD_SIZE, MESH_LOW_SIZE
from core.templates import generate_html, _make_hover, ANIMATION_BASE_DURATION_MS

# ─── View Functions ──────────────────────────────────────────────────

N_CLUSTERS = 3

def view_2d(longitude, latitude, magnitude, times, dates_num=None, depth=None):
    import plotly.express as px
    import pandas as pd
    
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
        hover_name=all_hover,
        zoom=12,
        labels={"lat": "Latitude", "lon": "Longitude", "size": "Magnitude"},
    )
    
    # Trace 0: Scatter
    fig.update_traces(
        marker=dict(
            color=magnitude,
            colorscale='Plasma',
            showscale=True,
            cmin=min(magnitude), cmax=max(magnitude),
            colorbar=dict(title="Magnitude", x=1.02, thickness=15, len=0.5)
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
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0}
    )
    return fig


def view_3d(longitude, latitude, magnitude, depth, times, dates_num=None):
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

    from sklearn.cluster import MiniBatchKMeans
    from sklearn.preprocessing import StandardScaler
    import plotly.express as px
    from scipy.spatial import ConvexHull
    
    # Calculate Clusters first to determine edges
    X_orig = np.column_stack((longitude, latitude, depth))
    if len(X_orig) >= N_CLUSTERS:
        X_scaled = StandardScaler().fit_transform(X_orig)
        kmeans = MiniBatchKMeans(n_clusters=N_CLUSTERS, random_state=42, n_init='auto', batch_size=1024).fit(X_scaled)
        labels = kmeans.labels_
    else:
        labels = np.zeros(len(X_orig), dtype=int)
        
    cluster_colors = px.colors.qualitative.Plotly
    
    # 1. Surface (Index 0)
    fig.add_trace(go.Surface(
        x=x_grid, y=y_grid, z=z_grid,
        surfacecolor=surfacecolor, colorscale=colorscale,
        showscale=False, opacity=0.9, hoverinfo='skip'
    ))

    # 2. Cluster Wireframes (Indices 1-5)
    # Using mode='lines' ensures they don't block mouse hover for internal points!
    for i in range(N_CLUSTERS):
        idx = labels == i
        pts = X_orig[idx]
        
        # We need at least 4 non-coplanar points for a 3D Hull
        if len(pts) > 4:
            try:
                # Downsample complex hulls for speed
                if len(pts) > 400:
                    sample_idx = np.random.choice(len(pts), 400, replace=False)
                    pts_hull = pts[sample_idx]
                else:
                    pts_hull = pts
                
                hull = ConvexHull(pts_hull)
                
                # Extract all edges from the simplices
                lx, ly, lz = [], [], []
                for s in hull.simplices:
                    # Each simplex is a triangle, add its 3 edges
                    for combo in [(0, 1), (1, 2), (2, 0)]:
                        lx.extend([pts_hull[s[combo[0]], 0], pts_hull[s[combo[1]], 0], None])
                        ly.extend([pts_hull[s[combo[0]], 1], pts_hull[s[combo[1]], 1], None])
                        lz.extend([pts_hull[s[combo[0]], 2], pts_hull[s[combo[1]], 2], None])

                fig.add_trace(go.Scatter3d(
                    x=lx, y=ly, z=lz,
                    mode='lines',
                    line=dict(color=cluster_colors[i % len(cluster_colors)], width=2),
                    opacity=0.4,
                    name=f'Cluster {i} Wireframe',
                    visible=False,
                    showlegend=False,
                    hoverinfo='skip'
                ))
            except Exception:
                # Fallback for degenerate cases
                fig.add_trace(go.Scatter3d(x=[], y=[], z=[], visible=False, hoverinfo='skip'))
        else:
            fig.add_trace(go.Scatter3d(x=[], y=[], z=[], visible=False, hoverinfo='skip'))

    # 3. Scatter Points (Indices 6 and 7)
    fig.add_trace(go.Scatter3d(
        x=longitude, y=latitude, z=depth,
        mode='markers', hovertext=all_hover,
        marker=dict(
            size=magnitude, sizemode='diameter', sizeref=0.12, # Slightly larger for easier hover
            color=depth, colorscale=[[0, 'red'], [1, 'blue']],
            showscale=True,
            cmin=min(depth), cmax=max(depth),
            colorbar=dict(title="Depth", x=1.02, thickness=15, len=0.4),
            line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
            opacity=0.9,
        ),
        name='Earthquakes (Mag)', visible=True,
        showlegend=False,
        hovertemplate='%{hovertext}<extra></extra>'
    ))

    if dates_num is not None:
        fig.add_trace(go.Scatter3d(
            x=longitude, y=latitude, z=depth,
            mode='markers', hovertext=all_hover,
            marker=dict(
                size=magnitude, sizemode='diameter', sizeref=0.15,
                color=dates_num, colorscale='Turbo',
                showscale=True,
                cmin=min(dates_num), cmax=max(dates_num),
                colorbar=dict(title="Days", x=1.02, thickness=15, len=0.4),
                line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
                opacity=0.9,
            ),
            name='Earthquakes (Date)', visible=False,
            showlegend=False,
            hovertemplate='%{hovertext}<extra></extra>'
        ))
    else:
        # Placeholder for trace 7 to maintain indexing
        fig.add_trace(go.Scatter3d(x=[], y=[], z=[], visible=False, hoverinfo='skip'))

    # 4. Cluster Solid Volumes (Indices 8-12)
    for i in range(N_CLUSTERS):
        idx = labels == i
        pts = X_orig[idx]
        if len(pts) > 4:
            try:
                if len(pts) > 400:
                    sample_idx = np.random.choice(len(pts), 400, replace=False)
                    pts_sample = pts[sample_idx]
                else:
                    pts_sample = pts
                
                fig.add_trace(go.Mesh3d(
                    x=pts_sample[:, 0], y=pts_sample[:, 1], z=pts_sample[:, 2],
                    color=cluster_colors[i % len(cluster_colors)],
                    opacity=0.15, alphahull=0,
                    name=f"Cluster {i} (Solid)",
                    visible=False,
                    showlegend=False,
                    hoverinfo='skip',
                    hovertemplate=None
                ))
            except Exception:
                fig.add_trace(go.Mesh3d(x=[], y=[], z=[], visible=False, hoverinfo='skip', showlegend=False))
        else:
            fig.add_trace(go.Mesh3d(x=[], y=[], z=[], visible=False, hoverinfo='skip', showlegend=False))

    # 5. Legend Proxies (Indices 13-17)
    for i in range(N_CLUSTERS):
        fig.add_trace(go.Scatter3d(
            x=[None], y=[None], z=[None],
            mode='markers',
            marker=dict(color=cluster_colors[i % len(cluster_colors)], size=10),
            name=f"Cluster {i}",
            visible=False,
            showlegend=True
        ))

    fig.update_layout(
        showlegend=False, # Toggled in JS
        scene=dict(
            xaxis=dict(title='Longitude', range=[x_grid[0], x_grid[-1]]),
            yaxis=dict(title='Latitude', range=[y_grid[-1], y_grid[0]]),
            zaxis=dict(title='Depth (km)', range=[min_depth, 0]),
            aspectmode='manual',
            aspectratio=dict(x=1, y=1, z=0.5),
        ),
        margin=dict(l=0, r=0, b=0, t=30),
    )
    return fig, labels


def get_3d_animated_figure(longitude, latitude, magnitude, depth, times,
                           on_progress=None, anim_mode='accumulation', window_days=5):
    def _report(msg):
        print(msg)
        if on_progress:
            on_progress(msg)

    _report("Preparing 3D animation data...")
    df = pd.DataFrame({
        'lon': longitude, 'lat': latitude,
        'mag': magnitude, 'dep': depth, 'time_str': times,
        'time': [
            datetime.strptime(t, "%Y-%m-%d %H:%M:%S.%f")
            if '.' in t
            else datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
            for t in times
        ],
    })

    df['date_num'] = (df['time'] - df['time'].min()).dt.total_seconds() / 86400.0
    df = df.sort_values('time').reset_index(drop=True)
    df['date'] = df['time'].dt.strftime('%Y-%m-%d')
    unique_dates = sorted(df['date'].unique())

    bbox = (df['lat'].min(), df['lon'].min(), df['lat'].max(), df['lon'].max())
    min_depth = df['dep'].min()

    _report("Building map mesh (HD + SD)...")
    x_high, y_high, z_high, mat_high, scale_high, map_data = build_map_mesh(
        bbox, MESH_HD_SIZE
    )

    # Calculate low-res grids
    original_w, original_h = map_data['img'].size
    scale_hd = max(1, max(original_w, original_h) / MESH_HD_SIZE)
    scale_ratio = MESH_HD_SIZE / MESH_LOW_SIZE
    new_w_low, new_h_low = int(original_w / (scale_hd * scale_ratio)), int(original_h / (scale_hd * scale_ratio))
    
    mat_low = np.array(PIL.Image.fromarray(mat_high).resize((new_w_low, new_h_low), resample=PIL.Image.Resampling.NEAREST))
    
    from core.geo_utils import _compute_grid
    n = 2 ** map_data['z']
    ts = map_data['tilesize']
    x_low, y_low = _compute_grid(new_w_low, new_h_low, scale_hd * scale_ratio, ts, map_data['xmin'], map_data['ymin'], n)
    z_low = np.zeros(mat_low.shape)

    mag_min, mag_max = df['mag'].min(), df['mag'].max()
    date_n_min, date_n_max = df['date_num'].min(), df['date_num'].max()

    initial_df = df.iloc[:0]
    initial_hover = []
    fig = go.Figure()

    fig.add_trace(go.Surface(
        x=x_low, y=y_low, z=z_low,
        surfacecolor=mat_low, colorscale=scale_high,
        showscale=False, opacity=0.9, hoverinfo='skip', visible=False,
        lighting=dict(ambient=1, diffuse=0, specular=0, roughness=1, fresnel=0),
    ))
    fig.add_trace(go.Surface(
        x=x_high, y=y_high, z=z_high,
        surfacecolor=mat_high, colorscale=scale_high,
        showscale=False, opacity=0.9, hoverinfo='skip', visible=True,
        lighting=dict(ambient=1, diffuse=0, specular=0, roughness=1, fresnel=0),
    ))
    fig.add_trace(go.Scatter3d(
        x=initial_df['lon'], y=initial_df['lat'], z=initial_df['dep'],
        mode='markers', hovertext=initial_hover, hoverinfo='text',
        marker=dict(
            size=initial_df['mag'], sizemode='diameter', sizeref=0.1,
            color=initial_df['mag'], colorscale='Plasma',
            showscale=True, cmin=mag_min, cmax=mag_max,
            colorbar=dict(title="Magnitude", x=1.02, thickness=15, len=0.4),
            line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
            opacity=0.8,
        ),
        name='Color: Magnitude', visible=True,
    ))
    fig.add_trace(go.Scatter3d(
        x=initial_df['lon'], y=initial_df['lat'], z=initial_df['dep'],
        mode='markers', hovertext=initial_hover, hoverinfo='text',
        marker=dict(
            size=initial_df['mag'], sizemode='diameter', sizeref=0.1,
            color=initial_df['date_num'], colorscale='Turbo',
            showscale=True, cmin=date_n_min, cmax=date_n_max,
            colorbar=dict(title="Days", x=1.02, thickness=15, len=0.4),
            line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
            opacity=0.8,
        ),
        name='Color: Date', visible=False,
        hovertemplate='%{hovertext}<extra></extra>'
    ))

    _report("Generating animation frames...")
    all_hover = _make_hover(df)
    arr_lon = df['lon'].values
    arr_lat = df['lat'].values
    arr_dep = df['dep'].values
    arr_mag = df['mag'].values
    arr_dnum = df['date_num'].values
    date_counts = df.groupby('date').size()

    frames = []
    
    # Pre-calculate cumulative indices
    cum = 0
    date_to_cum = {}
    for d in unique_dates:
        cum += date_counts[d]
        date_to_cum[d] = cum

    n_dates = len(unique_dates)

    for i, date in enumerate(unique_dates):
        end_idx = date_to_cum[date]
        
        if anim_mode == 'window':
            start_date_dt = pd.to_datetime(date) - pd.Timedelta(days=window_days-1)
            start_date_str = start_date_dt.strftime('%Y-%m-%d')
            
            start_idx = 0
            for d in unique_dates:
                if d < start_date_str:
                    start_idx = date_to_cum[d]
                else:
                    break
        else:
            start_idx = 0
            
        frames.append(go.Frame(
            data=[
                go.Scatter3d(
                    x=arr_lon[start_idx:end_idx], y=arr_lat[start_idx:end_idx], z=arr_dep[start_idx:end_idx],
                    hovertext=all_hover[start_idx:end_idx],
                    marker=dict(size=arr_mag[start_idx:end_idx], color=arr_mag[start_idx:end_idx], cmin=mag_min, cmax=mag_max),
                    hovertemplate='%{hovertext}<extra></extra>'
                ),
                go.Scatter3d(
                    x=arr_lon[start_idx:end_idx], y=arr_lat[start_idx:end_idx], z=arr_dep[start_idx:end_idx],
                    hovertext=all_hover[start_idx:end_idx],
                    marker=dict(size=arr_mag[start_idx:end_idx], color=arr_dnum[start_idx:end_idx], cmin=date_n_min, cmax=date_n_max, colorscale='Turbo'),
                    hovertemplate='%{hovertext}<extra></extra>'
                ),
            ],
            traces=[2, 3], name=date,
        ))
        if (i + 1) % 30 == 0 or i == n_dates - 1:
            _report(f"Frames: {i + 1}/{n_dates}")

    fig.frames = frames
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Longitude', range=[x_low[0], x_low[-1]]),
            yaxis=dict(title='Latitude', range=[y_low[-1], y_low[0]]),
            zaxis=dict(title='Depth (km)', range=[min_depth, 0]),
            aspectmode='manual', aspectratio=dict(x=1, y=1, z=0.5),
        ),
        sliders=[{"active": 0, "visible": False, "steps": [
            {"args": [[date], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate", "transition": {"duration": 0}}], "label": date, "method": "animate"}
            for date in unique_dates
        ]}],
        margin=dict(l=0, r=80, b=0, t=30),
    )
    return fig


def build_view_html(data, view_style, back_button=True, on_progress=None, anim_mode='accumulation', window_days=5):
    def _report(msg):
        if on_progress: on_progress(msg)

    lon, lat, mag, dep, times = data['longitude'], data['latitude'], data['magnitude'], data['depth'], data['times']

    def _get_dates_num():
        ts = [datetime.strptime(t, "%Y-%m-%d %H:%M:%S.%f") if '.' in t else datetime.strptime(t, "%Y-%m-%d %H:%M:%S") for t in times]
        min_t = min(ts)
        return [(t - min_t).total_seconds() / 86400.0 for t in ts]

    if view_style == 0:
        _report("Generating 2D map…")
        d_num = _get_dates_num()
        fig = view_2d(lon, lat, mag, times, dates_num=d_num, depth=dep)
        static_data = data.copy()
        static_data['dates_num'] = d_num
        static_data['hover'] = _make_hover(pd.DataFrame({'lon': lon, 'lat': lat, 'mag': mag, 'dep': dep, 'time_str': times}))
        static_data['mag_limit'] = [min(mag), max(mag)]
        static_data['date_limit'] = [min(d_num), max(d_num)]
        static_data['dep_limit'] = [min(dep), max(dep)]
        static_data['n_clusters'] = N_CLUSTERS
        return generate_html(fig, back_button=back_button, earthquake_data=static_data)
    elif view_style == 1:
        _report("Preparing 3D static view…")
        d_num = _get_dates_num()
        fig, labels = view_3d(lon, lat, mag, dep, times, dates_num=d_num)
        static_data = data.copy()
        static_data['dates_num'] = d_num
        static_data['cluster'] = labels.tolist()
        static_data['hover'] = _make_hover(pd.DataFrame({'lon': lon, 'lat': lat, 'mag': mag, 'dep': dep, 'time_str': times}))
        static_data['mag_limit'] = [min(mag), max(mag)]
        static_data['date_limit'] = [min(d_num), max(d_num)]
        static_data['dep_limit'] = [min(dep), max(dep)]
        static_data['n_clusters'] = N_CLUSTERS
        return generate_html(fig, back_button=back_button, earthquake_data=static_data)
    elif view_style == 2:
        fig = get_3d_animated_figure(lon, lat, mag, dep, times, on_progress=on_progress, anim_mode=anim_mode, window_days=window_days)
        return generate_html(fig, is_animated=True, back_button=back_button)
    else:
        raise ValueError(f"Invalid view style: {view_style}")