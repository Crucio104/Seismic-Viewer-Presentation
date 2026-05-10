import logging
import numpy as np
from datetime import datetime
from scipy.spatial import KDTree
from scipy.linalg import svd
import concurrent.futures
import os
from typing import Any

from core.config import KM_PER_DEGREE, SECONDS_PER_DAY

logger = logging.getLogger(__name__)

# --- Worker Data Management ---
_worker_data = {}

def _init_worker(pts_km: np.ndarray) -> None:
    """Initialize worker process with shared data once to avoid per-task serialization."""
    global _worker_data
    _worker_data['pts_km'] = pts_km

# --- Geological Math ---

def get_strike_dip(normal: np.ndarray) -> tuple[float, float, float]:
    """
    Convert a 3D normal vector [nx, ny, nz] (x=East, y=North, z=Down) 
    into geological parameters: Strike, Dip, Dip Direction.
    """
    # Ensure normal points down (z >= 0)
    if normal[2] < 0:
        normal = -normal
    
    # Dip: Angle with horizontal (degrees)
    # Since normal is unit length, cos(dip) = normal[2]
    dip = np.degrees(np.arccos(np.clip(normal[2], -1.0, 1.0)))
    
    # Dip Direction: Azimuth of the downward slope (degrees)
    dip_dir = (np.degrees(np.arctan2(normal[0], normal[1]))) % 360
    
    # Strike: Dip Direction - 90 (using Right Hand Rule: dip is to the right)
    strike = (dip_dir - 90) % 360
    
    return strike, dip, dip_dir

def fit_plane_ransac(points: np.ndarray, threshold: float = 0.05, max_iterations: int = 100, min_inliers: int = 3) -> tuple[np.ndarray | None, np.ndarray | None, float]:
    """
    Robust plane fitting using RANSAC for 3D points (Total Least Squares).
    Returns: (normal, centroid, planarity)
    """
    n_points = points.shape[0]
    if n_points < min_inliers:
        return None, None, 0.0
    
    # Use a fixed seed for stability across recalculations
    seed = int(np.abs(np.sum(points)) * 1000) % 4294967295
    rng = np.random.RandomState(seed)
    
    best_inliers = []
    
    # RANSAC Loop
    for _ in range(max_iterations):
        # Pick 3 random points
        idx = rng.choice(n_points, 3, replace=False)
        sample = points[idx]
        
        # Calculate candidate plane via cross product
        v1 = sample[1] - sample[0]
        v2 = sample[2] - sample[0]
        normal = np.cross(v1, v2)
        norm_len = np.linalg.norm(normal)
        
        if norm_len < 1e-8:
            continue 
            
        normal /= norm_len
        
        # Calculate orthogonal distances to plane
        dists = np.abs(np.dot(points, normal) - np.dot(sample[0], normal))
        inliers = np.where(dists < threshold)[0]
        if len(inliers) > len(best_inliers):
            best_inliers = inliers
            
    if len(best_inliers) < min_inliers:
        return None, None, 0.0
    
    # Refit using all inliers for maximum precision
    inlier_pts = points[best_inliers]
    centroid = np.mean(inlier_pts, axis=0)
    centered = inlier_pts - centroid
    _, s, vh = svd(centered)
    normal = vh[2, :]
    planarity = float((s[1] - s[2]) / s[0] if s[0] > 0 else 1.0)
    
    return normal, centroid, planarity

def _format_plane_geometry(
    normal: np.ndarray, 
    centroid_km: np.ndarray, 
    planarity: float,
    c_lon: float, 
    c_lat: float, 
    lon_to_km: float, 
    radius: float
) -> dict[str, Any]:
    """Helper to convert plane vectors into Plotly-ready coordinates and metadata."""
    strike_val, dip_val, dd_val = get_strike_dip(normal)
    
    # Basis vectors for the plane
    u = np.cross(normal, [0, 0, 1])
    if np.linalg.norm(u) < 1e-6:
        u = np.array([1, 0, 0])
    else:
        u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    v /= np.linalg.norm(v)
    
    # Square vertices in KM
    sq_verts_km = np.array([
        centroid_km - radius*u - radius*v,
        centroid_km + radius*u - radius*v,
        centroid_km + radius*u + radius*v,
        centroid_km - radius*u + radius*v
    ])
    
    # Convert to Lon/Lat/Depth
    v_lon = (sq_verts_km[:, 0] / lon_to_km) + (c_lon - centroid_km[0]/lon_to_km)
    v_lat = (sq_verts_km[:, 1] / KM_PER_DEGREE) + (c_lat - centroid_km[1]/KM_PER_DEGREE)
    
    # Plane Equation: Ax + By + Cz + D = 0
    eq_a = normal[0] * lon_to_km
    eq_b = normal[1] * KM_PER_DEGREE
    eq_c = normal[2]
    eq_d = -(eq_a * c_lon + eq_b * c_lat + eq_c * centroid_km[2])

    return {
        'x': v_lon.tolist(), 'y': v_lat.tolist(), 'z': sq_verts_km[:, 2].tolist(),
        'planarity': float(planarity), 'strike': float(strike_val),
        'dip': float(dip_val), 'dip_dir': float(dd_val),
        'equation': { 'a': float(eq_a), 'b': float(eq_b), 'c': float(eq_c), 'd': float(eq_d) }
    }

# --- Structural Analysis ---

def calculate_structural_planes(
    pts_km: np.ndarray, 
    active_grid: list[tuple],
    radius_km: float, 
    min_pts: int, 
    valid_range: tuple[int, int] | None = None,
    origin_lon: float = 0, 
    origin_lat: float = 0,
    lon_to_km: float = 1,
    date_tag: str = ""
) -> list[dict[str, Any]]:
    """Fits planes to points within cylinders using RANSAC."""
    planes = []
    ransac_threshold = max(0.02, radius_km * 0.1)
    start_idx, end_idx = valid_range if valid_range else (0, len(pts_km))

    for ix, iy, cx, cy, global_indices in active_grid:
        valid_indices = [i for i in global_indices if start_idx <= i < end_idx]
        
        if len(valid_indices) >= min_pts:
            subset = pts_km[valid_indices]
            normal, centroid, planarity = fit_plane_ransac(subset, threshold=ransac_threshold, min_inliers=min_pts)
                
            if normal is None or centroid is None:
                continue

            c_lon = (centroid[0] / lon_to_km) + origin_lon
            c_lat = (centroid[1] / KM_PER_DEGREE) + origin_lat 

            plane_data = _format_plane_geometry(
                normal, centroid, planarity, 
                c_lon, c_lat, lon_to_km, radius_km
            )
            plane_data['grid_id'] = f"{ix}_{iy}_{date_tag}" if date_tag else f"{ix}_{iy}"
            planes.append(plane_data)
    return planes

def _worker_calculate_planes(args: tuple) -> tuple[str, list[dict[str, Any]]]:
    date_str, start_idx, end_idx, active_grid, radius_km, min_pts, origin_lon, origin_lat, lon_to_km = args
    pts_km = _worker_data['pts_km']
    planes = calculate_structural_planes(
        pts_km, active_grid, radius_km, min_pts, 
        valid_range=(start_idx, end_idx),
        origin_lon=origin_lon, origin_lat=origin_lat, 
        lon_to_km=lon_to_km, date_tag=date_str
    )
    return date_str, planes

def get_animation_planes(data: dict[str, Any], radius_km: float, min_pts: int, window_days: int) -> dict[str, list[dict[str, Any]]]:
    """Calculates structural planes for animation using multiprocessing."""
    lon = np.array(data['longitude'], dtype=np.float32)
    lat = np.array(data['latitude'], dtype=np.float32)
    dep = np.array(data['depth'], dtype=np.float32)
    dates_unique = data['visual_pack']['unique_dates']
    date_to_cum = data['visual_pack']['date_to_cum']

    origin_lat = np.mean(lat)
    origin_lon = np.mean(lon)
    lon_to_km = KM_PER_DEGREE * np.cos(np.radians(origin_lat))
    lon_km = (lon - origin_lon) * lon_to_km
    lat_km = (lat - origin_lat) * KM_PER_DEGREE
    
    overlap = 0.2
    spacing = radius_km * (2.0 - overlap)
    grid_x = np.arange(np.min(lon_km), np.max(lon_km) + spacing, spacing)
    grid_y = np.arange(np.min(lat_km), np.max(lat_km) + spacing, spacing)

    pts_km = np.column_stack((lon_km, lat_km, dep))
    tree = KDTree(pts_km[:, :2])
    
    active_grid = []
    for ix, cx in enumerate(grid_x):
        for iy, cy in enumerate(grid_y):
            indices = tree.query_ball_point([cx, cy], radius_km)
            if len(indices) >= min_pts:
                active_grid.append((ix, iy, cx, cy, indices))
    
    tasks = []
    dates_ts = np.array([datetime.strptime(d, '%Y-%m-%d').timestamp() for d in dates_unique])
    
    for i, date_str in enumerate(dates_unique):
        end_idx = date_to_cum[date_str]
        cutoff_ts = dates_ts[i] - (window_days - 1) * SECONDS_PER_DAY
        start_date_idx = np.searchsorted(dates_ts, cutoff_ts)
        start_idx = 0
        if start_date_idx > 0:
            prev_date_str = dates_unique[start_date_idx - 1]
            start_idx = date_to_cum[prev_date_str]
        
        tasks.append((
            date_str, start_idx, end_idx, active_grid, radius_km, min_pts, 
            float(origin_lon), float(origin_lat), float(lon_to_km)
        ))

    results = {}
    max_workers = min(os.cpu_count() or 4, 8)
    
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=_init_worker,
        initargs=(pts_km,)
    ) as executor:
        for date_str, planes in executor.map(_worker_calculate_planes, tasks):
            results[date_str] = planes
            
    return results

# --- Clustering Analysis ---

def perform_clustering(pts_km: np.ndarray, method: str = 'kmeans', params: dict[str, Any] | None = None, prev_centroids: np.ndarray | None = None) -> tuple[np.ndarray, int, np.ndarray | None]:
    """
    Perform clustering (KMeans or DBSCAN) on 3D points.
    Returns: (labels, n_clusters, centroids)
    """
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import MiniBatchKMeans, DBSCAN
    
    params = params or {}
    if len(pts_km) == 0:
        return np.array([]), 0, None

    centroids = None
    if method == 'dbscan':
        eps_km = float(params.get('dbscan_eps', 500)) / 1000.0
        min_samples = int(params.get('dbscan_min_samples', 5))
        db = DBSCAN(eps=eps_km, min_samples=min_samples, metric='euclidean').fit(pts_km)
        labels = db.labels_
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        
        # DBSCAN doesn't have true centroids, but we can return mean of points for tracking
        if n_clusters > 0:
            centroids = np.array([np.mean(pts_km[labels == i], axis=0) for i in range(n_clusters)])
    else:
        n_clusters_req = int(params.get('kmeans_clusters', 3))
        if len(pts_km) >= n_clusters_req:
            # For stabilization, we use previous centroids as initialization
            init_val = 'k-means++'
            n_init_val = 'auto'
            if prev_centroids is not None and prev_centroids.shape == (n_clusters_req, pts_km.shape[1]):
                init_val = prev_centroids
                n_init_val = 1
            
            kmeans = MiniBatchKMeans(n_clusters=n_clusters_req, random_state=42, init=init_val, n_init=n_init_val).fit(pts_km)
            labels = kmeans.labels_
            n_clusters = n_clusters_req
            centroids = kmeans.cluster_centers_
        else:
            labels = np.zeros(len(pts_km), dtype=int)
            n_clusters = 1
            centroids = np.array([np.mean(pts_km, axis=0)]) if len(pts_km) > 0 else None

    display_labels = labels.copy()
    if method == 'kmeans' and float(params.get('kmeans_max_dist', 0)) > 0:
        max_d = float(params.get('kmeans_max_dist', 0))
        for i in range(n_clusters):
            idx = (labels == i)
            if not np.any(idx):
                continue
            center_km = centroids[i]
            dists = np.sqrt(np.sum((pts_km[idx] - center_km)**2, axis=1))
            display_labels[np.where(idx)[0][dists > max_d]] = -1
            
    return display_labels, n_clusters, centroids

def project_to_km(lon: np.ndarray, lat: np.ndarray, dep: np.ndarray, origin_lat: float, origin_lon: float) -> np.ndarray:
    """Standardized projection from Lon/Lat/Dep to KM space."""
    from core.config import KM_PER_DEGREE
    lon_to_km = KM_PER_DEGREE * np.cos(np.radians(origin_lat))
    lat_to_km = KM_PER_DEGREE
    return np.column_stack((
        (lon - origin_lon) * lon_to_km,
        (lat - origin_lat) * lat_to_km,
        dep
    ))

def _worker_calculate_clustering(args: tuple) -> tuple[str, list[int], list[dict[str, Any]]]:
    date_str, start_idx, end_idx, method, params, origin_lon, origin_lat, lon_to_km = args
    pts_km = _worker_data['pts_km']
    pts_subset = pts_km[start_idx:end_idx]
    
    if len(pts_subset) == 0:
        return date_str, [], []
    
    display_labels, n_clusters, _ = perform_clustering(pts_subset, method, params)

    planes = []
    show_planes = params.get('show_cluster_planes', False)
    if show_planes:
        for i in range(n_clusters):
            idx = (display_labels == i)
            pts = pts_subset[idx]
            if len(pts) >= 4:
                normal, centroid_km, planarity = fit_plane_ransac(pts, threshold=0.15)
                if normal is not None and centroid_km is not None:
                    avg_dist = np.mean(np.linalg.norm(pts - centroid_km, axis=1))
                    radius_eff = max(0.2, 5 * avg_dist)
                    
                    c_lon = (centroid_km[0] / lon_to_km) + origin_lon
                    c_lat = (centroid_km[1] / KM_PER_DEGREE) + origin_lat
                    
                    plane_data = _format_plane_geometry(
                        normal, centroid_km, planarity,
                        c_lon, c_lat, lon_to_km, radius_eff
                    )
                    plane_data['grid_id'] = f"cluster_{i}_{date_str}"
                    planes.append(plane_data)
    
    return date_str, display_labels.tolist(), planes

def match_labels_globally(current_labels: np.ndarray, current_global_indices: np.ndarray, 
                          prev_labels_map: np.ndarray, next_label_id: int) -> tuple[np.ndarray, int]:
    """
    Matches current labels to previous ones using global array mapping for extreme speed.
    """
    new_labels = np.full_like(current_labels, -1)
    unique_curr = [l for l in np.unique(current_labels) if l != -1]
    
    for l in unique_curr:
        mask = (current_labels == l)
        l_indices = current_global_indices[mask]
        
        # Vectorized lookup in the global labels map
        matched_prev = prev_labels_map[l_indices]
        valid_prev = matched_prev[matched_prev != -1]
        
        if valid_prev.size > 0:
            # Majority vote
            vals, counts = np.unique(valid_prev, return_counts=True)
            best_prev_label = int(vals[np.argmax(counts)])
            new_labels[mask] = best_prev_label
        else:
            new_labels[mask] = next_label_id
            next_label_id += 1
            
    return new_labels, next_label_id

def get_animation_clustering(data: dict[str, Any], method: str, params: dict[str, Any], plane_step: int = 5) -> dict[str, Any]:
    """
    Calculates clustering for EVERY frame with temporal label stability.
    Uses global index matching for extreme performance.
    """
    dates_unique = data['visual_pack']['unique_dates']
    date_to_cum = data['visual_pack']['date_to_cum']
    anim_mode = data.get('anim_mode', 'accumulation')
    window_days = data.get('window_days', 5)

    # Pre-convert all data to numpy for speed
    lon = np.array(data['longitude'])
    lat = np.array(data['latitude'])
    dep = np.array(data['depth'])
    mags = np.array(data['magnitude'])
    
    origin_lat = data.get('origin_lat', np.mean(lat))
    origin_lon = data.get('origin_lon', np.mean(lon))
    
    from core.config import KM_PER_DEGREE
    lon_to_km = KM_PER_DEGREE * np.cos(np.radians(origin_lat))
    pts_km = project_to_km(lon, lat, dep, origin_lat, origin_lon)

    results = {}
    
    # Fast Stability State: use a fixed-size array instead of a dict
    global_labels_map = np.full(len(pts_km), -1, dtype=int)
    next_label_id = 0
    prev_centroids = None
    has_initialized_labels = False
    last_valid_planes = []

    # Get filters
    min_mag = float(params.get('mag_min', -10.0))
    max_mag = float(params.get('mag_max', 10.0))
    max_dep = float(params.get('dep_max', 1000.0))
    min_dep = float(params.get('dep_min', -100.0))

    # Optimization: pre-calculate indices for all dates
    date_indices = []
    if anim_mode == 'accumulation':
        for d in dates_unique:
            date_indices.append((0, date_to_cum[d]))
    else:
        # Window mode pre-calculation
        from datetime import datetime, timedelta
        dt_objs = [datetime.strptime(d, '%Y-%m-%d') for d in dates_unique]
        for i, date_str in enumerate(dates_unique):
            curr_dt = dt_objs[i]
            cutoff_dt = curr_dt - timedelta(days=window_days-1)
            cutoff_str = cutoff_dt.strftime('%Y-%m-%d')
            
            s_idx = 0
            for j, d in enumerate(dates_unique):
                if d >= cutoff_str:
                    s_idx = date_to_cum[dates_unique[j-1]] if j > 0 else 0
                    break
            date_indices.append((s_idx, date_to_cum[date_str]))

    for i, (start_idx, end_idx) in enumerate(date_indices):
        date_str = dates_unique[i]
        
        pts_raw = pts_km[start_idx:end_idx]
        mag_raw = mags[start_idx:end_idx]
        dep_raw = dep[start_idx:end_idx]
        indices_raw = np.arange(start_idx, end_idx)
        
        mask = (mag_raw >= min_mag) & (mag_raw <= max_mag) & (dep_raw >= min_dep) & (dep_raw <= max_dep)
        
        pts_subset = pts_raw[mask]
        global_indices = indices_raw[mask]
        final_labels = np.full(len(pts_raw), -1)
        
        if len(pts_subset) < 3:
            results[date_str] = {'labels': final_labels.tolist(), 'planes': []}
            global_labels_map[global_indices] = -1
            continue

        # 1. Perform Raw Clustering
        labels, n_clusters, centroids = perform_clustering(pts_subset, method, params, prev_centroids=prev_centroids)
        prev_centroids = centroids
        
        # 2. Match Labels for Stability
        if n_clusters > 0 and not has_initialized_labels:
            next_label_id = n_clusters
            matched_labels = labels
            global_labels_map[global_indices] = labels
            has_initialized_labels = True
        elif has_initialized_labels:
            matched_labels, next_label_id = match_labels_globally(
                labels, global_indices, global_labels_map, next_label_id
            )
            global_labels_map[global_indices] = matched_labels
        else:
            matched_labels = labels
            global_labels_map[global_indices] = labels

        final_labels[mask] = matched_labels

        # 3. Structural Planes (Persistent between steps)
        if (i % plane_step == 0):
            current_planes = []
            unique_matched = [l for l in np.unique(matched_labels) if l != -1]
            for cluster_idx in unique_matched:
                cl_mask = (matched_labels == cluster_idx)
                pts = pts_subset[cl_mask]
                if len(pts) >= 4:
                    normal, centroid_km, planarity = fit_plane_ransac(pts, threshold=0.15)
                    if normal is not None and centroid_km is not None:
                        c_lon = (centroid_km[0] / lon_to_km) + origin_lon
                        c_lat = (centroid_km[1] / KM_PER_DEGREE) + origin_lat
                        
                        plane_data = _format_plane_geometry(
                            normal, centroid_km, planarity,
                            c_lon, c_lat, lon_to_km, max(0.2, 5 * np.mean(np.linalg.norm(pts - centroid_km, axis=1)))
                        )
                        plane_data['grid_id'] = f"cluster_{cluster_idx}_{date_str}"
                        current_planes.append(plane_data)
            last_valid_planes = current_planes
        
        # Use the latest valid planes to fill the gap frames
        results[date_str] = {'labels': final_labels.tolist(), 'planes': last_valid_planes}
            
    return results
