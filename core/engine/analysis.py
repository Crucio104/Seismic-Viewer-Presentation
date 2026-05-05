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

def perform_clustering(pts_km: np.ndarray, method: str = 'kmeans', params: dict[str, Any] | None = None) -> tuple[np.ndarray, int]:
    """Perform clustering (KMeans or DBSCAN) on 3D points."""
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import MiniBatchKMeans, DBSCAN
    
    params = params or {}
    if len(pts_km) == 0:
        return np.array([]), 0

    if method == 'dbscan':
        eps_km = float(params.get('dbscan_eps', 500)) / 1000.0
        min_samples = int(params.get('dbscan_min_samples', 5))
        db = DBSCAN(eps=eps_km, min_samples=min_samples, metric='euclidean').fit(pts_km)
        labels = db.labels_
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        if n_clusters == 0:
            n_clusters = 1
            labels = np.zeros(len(pts_km), dtype=int)
    else:
        n_clusters_req = int(params.get('kmeans_clusters', 3))
        if len(pts_km) >= n_clusters_req:
            X_scaled = StandardScaler().fit_transform(pts_km)
            kmeans = MiniBatchKMeans(n_clusters=n_clusters_req, random_state=42, n_init='auto').fit(X_scaled)
            labels = kmeans.labels_
            n_clusters = n_clusters_req
        else:
            labels = np.zeros(len(pts_km), dtype=int)
            n_clusters = 1

    display_labels = labels.copy()
    if method == 'kmeans' and float(params.get('kmeans_max_dist', 0)) > 0:
        max_d = float(params.get('kmeans_max_dist', 0))
        for i in range(n_clusters):
            idx = (labels == i)
            if not np.any(idx):
                continue
            center_km = np.mean(pts_km[idx], axis=0)
            dists = np.sqrt(np.sum((pts_km[idx] - center_km)**2, axis=1))
            display_labels[np.where(idx)[0][dists > max_d]] = -1
            
    return display_labels, n_clusters

def _worker_calculate_clustering(args: tuple) -> tuple[str, list[int], list[dict[str, Any]]]:
    date_str, start_idx, end_idx, method, params, origin_lon, origin_lat, lon_to_km = args
    pts_km = _worker_data['pts_km']
    pts_subset = pts_km[start_idx:end_idx]
    
    if len(pts_subset) == 0:
        return date_str, [], []
    
    display_labels, n_clusters = perform_clustering(pts_subset, method, params)

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

def get_animation_clustering(data: dict[str, Any], method: str, params: dict[str, Any], step_frames: int) -> dict[str, Any]:
    """Calculates clustering and planes for animation steps."""
    lon = np.array(data['longitude'], dtype=np.float32)
    lat = np.array(data['latitude'], dtype=np.float32)
    dep = np.array(data['depth'], dtype=np.float32)
    dates_unique = data['visual_pack']['unique_dates']
    date_to_cum = data['visual_pack']['date_to_cum']
    anim_mode = data.get('anim_mode', 'accumulation')
    window_days = data.get('window_days', 5)

    origin_lat = np.mean(lat)
    origin_lon = np.mean(lon)
    lon_to_km = KM_PER_DEGREE * np.cos(np.radians(origin_lat))
    lon_km = (lon - origin_lon) * lon_to_km
    lat_km = (lat - origin_lat) * KM_PER_DEGREE
    pts_km = np.column_stack((lon_km, lat_km, dep))

    tasks = []
    dates_ts = np.array([datetime.strptime(d, '%Y-%m-%d').timestamp() for d in dates_unique])
    
    for i in range(0, len(dates_unique), step_frames):
        date_str = dates_unique[i]
        end_idx = date_to_cum[date_str]
        start_idx = 0
        if anim_mode == 'window':
            cutoff_ts = dates_ts[i] - (window_days - 1) * SECONDS_PER_DAY
            start_date_idx = np.searchsorted(dates_ts, cutoff_ts)
            if start_date_idx > 0:
                prev_date_str = dates_unique[start_date_idx - 1]
                start_idx = date_to_cum[prev_date_str]
        
        tasks.append((
            date_str, start_idx, end_idx, method, params, 
            float(origin_lon), float(origin_lat), float(lon_to_km)
        ))

    results = {}
    max_workers = min(os.cpu_count() or 4, 8)
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=_init_worker,
        initargs=(pts_km,)
    ) as executor:
        for date_str, labels, planes in executor.map(_worker_calculate_clustering, tasks):
            results[date_str] = {'labels': labels, 'planes': planes}
            
    return results
