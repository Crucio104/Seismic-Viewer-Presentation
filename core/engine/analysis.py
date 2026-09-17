import bisect
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import logging
import os
import time
from typing import Any

import numpy as np
from scipy.linalg import svd
from scipy.spatial import ConvexHull, KDTree
from sklearn.cluster import DBSCAN, HDBSCAN, MiniBatchKMeans
from sklearn.neighbors import NearestNeighbors

from core.config import KM_PER_DEGREE

logger = logging.getLogger(__name__)

# --- Worker Data Management ---
_worker_data = {}
_worker_clustering_data = {}

def _init_worker(pts_km: np.ndarray) -> None:
    """Initialize worker process with shared data once to avoid per-task serialization."""
    _worker_data['pts_km'] = pts_km

def _init_clustering_worker(data: dict[str, Any]) -> None:
    """Initialize worker process with shared clustering data once."""
    global _worker_clustering_data
    _worker_clustering_data = data

# --- Geological Math ---

def get_strike_dip(normal: np.ndarray) -> tuple[float, float, float]:
    """
    Convert a 3D normal vector [nx, ny, nz] into geological parameters: Strike, Dip, Dip Direction.
    Coordinate reference frame: x=East (km), y=North (km), z=Up/Elevation (km, subterranean z <= 0).
    Under this convention, for an upward-pointing normal (nz >= 0), the horizontal projection
    [nx, ny] points along the downward slope azimuth (Dip Direction).
    """
    n_len = np.linalg.norm(normal)
    if n_len < 1e-12:
        return 0.0, 0.0, 0.0
    normal = normal / n_len

    # Ensure normal points upward (z >= 0)
    if normal[2] < 0:
        normal = -normal
    
    # Dip: Angle between the fault plane and the horizontal (degrees, 0 to 90)
    dip = float(np.degrees(np.arccos(np.clip(normal[2], -1.0, 1.0))))
    
    # Dip Direction: Azimuth of the downward slope (0 to 360 degrees from North)
    dip_dir = float((np.degrees(np.arctan2(normal[0], normal[1]))) % 360)
    
    # Strike: Azimuth along strike using Right-Hand Rule (RHR, dip is to the right)
    strike = float((dip_dir - 90) % 360)
    
    return strike, dip, dip_dir

def fit_plane_ransac(points: np.ndarray, threshold: float = 0.05, max_iterations: int = 100, min_inliers: int = 3) -> tuple[np.ndarray | None, np.ndarray | None, float]:
    """
    Robust plane fitting using RANSAC for 3D points (Total Least Squares).
    Returns: (normal, centroid, planarity)
    """
    points = np.ascontiguousarray(points, dtype=np.float64)
    n_points = points.shape[0]
    if n_points < min_inliers:
        return None, None, 0.0
    
    # Use a fixed seed for stability across recalculations
    seed = int(np.abs(np.sum(points)) * 1000) % 4294967295
    rng = np.random.default_rng(seed)
    
    best_inliers = []
    best_loss = float('inf')
    best_inlier_count = 0
    
    # Pre-generate candidate triplets in a single vectorised call to avoid repeated Python RNG dispatch
    triplet_indices = rng.integers(0, n_points, size=(max_iterations, 3))
    
    # RANSAC Loop
    for it in range(max_iterations):
        idx = triplet_indices[it]
        # Skip degenerate triplets
        if idx[0] == idx[1] or idx[0] == idx[2] or idx[1] == idx[2]:
            continue
        sample = points[idx]
        
        # Calculate candidate plane via cross product
        v1 = sample[1] - sample[0]
        v2 = sample[2] - sample[0]
        normal = np.cross(v1, v2)
        norm_len = np.linalg.norm(normal)
        
        if norm_len < 1e-8:
            continue 
            
        normal /= norm_len
        
        # Calculate orthogonal distances to plane (vectorized BLAS)
        dists = np.abs(np.dot(points, normal) - np.dot(sample[0], normal))
        
        inliers = np.where(dists < threshold)[0]
        n_inliers = len(inliers)
        
        # Standard RANSAC: maximize inlier support, tie-break by inlier mean residual
        if n_inliers >= min_inliers:
            inlier_loss = float(np.mean(dists[inliers]))
            if n_inliers > best_inlier_count or (n_inliers == best_inlier_count and inlier_loss < best_loss):
                best_inlier_count = n_inliers
                best_loss = inlier_loss
                best_inliers = inliers
                # Early consensus exit when >= 90% of points are inliers
                if n_inliers >= int(0.90 * n_points):
                    break
            
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
    
    # Rigorous seismotectonic basis vectors:
    # u: Strike vector (horizontal unit vector pointing along strike azimuth)
    strike_rad = np.radians(strike_val)
    u = np.array([np.sin(strike_rad), np.cos(strike_rad), 0.0], dtype=np.float64)
    u_norm = np.linalg.norm(u)
    if u_norm > 1e-6:
        u /= u_norm
    else:
        u = np.array([1.0, 0.0, 0.0], dtype=np.float64)

    # v: Down-dip vector (pointing along the maximum downward slope of the fault plane)
    # v is perpendicular to strike and in the plane (cross product u x normal, pointing downwards)
    v = np.cross(u, normal)
    v_norm = np.linalg.norm(v)
    if v_norm > 1e-6:
        v /= v_norm
    else:
        v = np.array([0.0, 1.0, 0.0], dtype=np.float64)

    # Square patch vertices in KM (oriented with strike along u and dip along v)
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

    for ix, iy, _cx, _cy, global_indices in active_grid:
        if isinstance(global_indices, np.ndarray):
            left = int(np.searchsorted(global_indices, start_idx))
            right = int(np.searchsorted(global_indices, end_idx))
            if right - left < min_pts:
                continue
            valid_indices = global_indices[left:right]
        else:
            valid_indices = [i for i in global_indices if start_idx <= i < end_idx]
            if len(valid_indices) < min_pts:
                continue
        
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

def get_animation_planes(data: dict[str, Any], radius_km: float, min_pts: int, window_days: int, anim_mode: str = 'accumulation', step_days: int = 7) -> dict[str, list[dict[str, Any]]]:
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
                sorted_idx = np.sort(np.asarray(indices, dtype=np.int32))
                active_grid.append((ix, iy, cx, cy, sorted_idx))
    
    tasks = []
    
    # Get frame indices using the same logic as clustering
    dates_unique, date_indices = _get_frame_dates_and_indices(dates_unique, date_to_cum, anim_mode, window_days, step_days)
    
    for i, date_str in enumerate(dates_unique):
        start_idx, end_idx = date_indices[i]
        
        tasks.append((
            date_str, start_idx, end_idx, active_grid, radius_km, min_pts, 
            float(origin_lon), float(origin_lat), float(lon_to_km)
        ))

    results = {}
    _init_worker(pts_km)
    try:
        if len(tasks) <= 12 or len(pts_km) < 1500:
            for t in tasks:
                date_str, planes = _worker_calculate_planes(t)
                results[date_str] = planes
        else:
            max_workers = min(os.cpu_count() or 4, 8)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for date_str, planes in executor.map(_worker_calculate_planes, tasks):
                    results[date_str] = planes
    finally:
        _worker_data.clear()
            
    return results

# --- Clustering Analysis ---

def perform_clustering(pts_km: np.ndarray, method: str = 'dbscan', params: dict[str, Any] | None = None, prev_centroids: np.ndarray | None = None, dates_num: np.ndarray | list[float] | None = None) -> tuple[np.ndarray, int, np.ndarray | None]:
    """
    Perform 3D or 4D spatio-temporal clustering (DBSCAN, HDBSCAN, or KMeans).
    If params['use_time'] is True and dates_num is provided, clusters in 4D space-time
    with the temporal coordinate scaled to match the physical correlation time window.
    Returns: (labels, n_clusters, centroids)
    """
    params = params or {}
    if len(pts_km) == 0:
        return np.array([]), 0, None

    # Spatio-Temporal 4D scaling
    use_time = bool(params.get('use_time', False))
    if 'time_window_hours' in params:
        time_window_hours = float(params['time_window_hours'])
    elif 'time_window' in params:
        time_window_hours = float(params['time_window'])
    elif 'time_window_days' in params:
        time_window_hours = float(params['time_window_days']) * 24.0
    else:
        time_window_hours = 72.0

    if time_window_hours <= 0:
        time_window_hours = 72.0

    time_window_days = time_window_hours / 24.0

    if method == 'dbscan':
        eps_km = float(params.get('dbscan_eps', 500)) / 1000.0
        d_ref = eps_km
    elif method == 'hdbscan':
        eps_m = float(params.get('hdbscan_cluster_selection_epsilon', params.get('hdbscan_eps', 0.0)))
        d_ref = (eps_m / 1000.0) if eps_m > 0 else 0.5
    else:
        d_ref = 1.0

    if use_time and dates_num is not None and len(dates_num) == len(pts_km):
        t_arr = np.asarray(dates_num, dtype=float)
        time_scale = d_ref / time_window_days
        t_scaled = (t_arr - t_arr[0]) * time_scale
        features = np.column_stack((pts_km, t_scaled))
    else:
        features = pts_km

    centroids = None
    if method == 'dbscan':
        eps_km = float(params.get('dbscan_eps', 500)) / 1000.0
        min_samples = int(params.get('dbscan_min_samples', 5))
        db = DBSCAN(eps=eps_km, min_samples=min_samples, metric='euclidean').fit(features)
        labels = db.labels_
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        
        # DBSCAN centroids in 3D spatial space
        if n_clusters > 0:
            centroids = np.array([np.mean(pts_km[labels == i], axis=0) if np.any(labels == i) else np.zeros(pts_km.shape[1]) for i in range(n_clusters)])
    elif method == 'hdbscan':
        n_pts = len(features)
        if n_pts < 3:
            return np.full(n_pts, -1, dtype=int), 0, None

        min_cluster_size = int(params.get('hdbscan_min_cluster_size', 5))
        min_cluster_size = min(max(2, min_cluster_size), n_pts)

        min_samples = params.get('hdbscan_min_samples')
        if min_samples is not None and str(min_samples).strip() != "":
            min_samples = min(max(1, int(min_samples)), n_pts)
        else:
            min_samples = None
        
        eps_m = float(params.get('hdbscan_cluster_selection_epsilon', params.get('hdbscan_eps', 0.0)))
        cluster_selection_epsilon = (eps_m / 1000.0) if eps_m > 0 else 0.0
        
        hdb = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            cluster_selection_epsilon=cluster_selection_epsilon,
            cluster_selection_method='eom',
            allow_single_cluster=True,
            metric='euclidean',
            copy=True
        ).fit(features)
        labels = hdb.labels_
        unique_labels = sorted(set(labels) - {-1})
        n_clusters = len(unique_labels)
        if n_clusters > 0:
            centroids = np.array([np.mean(pts_km[labels == i], axis=0) if np.any(labels == i) else np.zeros(pts_km.shape[1]) for i in unique_labels])
    else:
        n_clusters_req = int(params.get('kmeans_clusters', 3))
        if len(features) >= n_clusters_req:
            init_val = 'k-means++'
            n_init_val = 'auto'
            if prev_centroids is not None and prev_centroids.shape == (n_clusters_req, features.shape[1]):
                init_val = prev_centroids
                n_init_val = 1
            
            kmeans = MiniBatchKMeans(n_clusters=n_clusters_req, random_state=42, init=init_val, n_init=n_init_val).fit(features)
            labels = kmeans.labels_
            n_clusters = n_clusters_req
            centroids = np.array([np.mean(pts_km[labels == i], axis=0) if np.any(labels == i) else np.zeros(pts_km.shape[1]) for i in range(n_clusters)])
        else:
            labels = np.zeros(len(pts_km), dtype=int)
            n_clusters = 1
            centroids = np.array([np.mean(pts_km, axis=0)]) if len(pts_km) > 0 else None

    display_labels = labels.copy()
    if method == 'kmeans' and float(params.get('kmeans_max_dist', 0)) > 0:
        max_d = float(params.get('kmeans_max_dist', 0)) / 1000.0
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
    lon_to_km = KM_PER_DEGREE * np.cos(np.radians(origin_lat))
    lat_to_km = KM_PER_DEGREE
    return np.column_stack((
        (lon - origin_lon) * lon_to_km,
        (lat - origin_lat) * lat_to_km,
        dep
    ))


def match_labels_globally(current_labels: np.ndarray, current_global_indices: np.ndarray,
                          prev_labels_map: np.ndarray, next_label_id: int) -> tuple[np.ndarray, int]:
    """
    Matches current labels to previous ones using global array mapping.
    Allows splitting: if multiple current clusters match the same previous label,
    only the best match keeps it, others get a new ID.
    """
    new_labels = np.full_like(current_labels, -1)
    unique_curr = [label_id for label_id in np.unique(current_labels) if label_id != -1]
    
    used_prev_labels = set()
    
    # First pass: try to match clusters that have a clear majority previous label
    for label_id in unique_curr:
        mask = (current_labels == label_id)
        l_indices = current_global_indices[mask]
        
        # OPTIMIZATION: Stochastic matching. 
        # Sampling 200 points is more than enough to find the majority label 
        # and it's VASTLY faster than analyzing thousands of points per frame.
        if len(l_indices) > 200:
            sample_indices = np.random.choice(l_indices, 200, replace=False)
        else:
            sample_indices = l_indices

        matched_prev = prev_labels_map[sample_indices]
        valid_prev = matched_prev[matched_prev != -1]
        
        if valid_prev.size > 0:
            vals, counts = np.bincount(valid_prev).nonzero(), np.bincount(valid_prev)
            # Filter out zero counts and get unique values
            nz = counts > 0
            vals = np.arange(len(counts))[nz]
            counts = counts[nz]
            
            sorted_indices = np.argsort(-counts)
            for idx in sorted_indices:
                candidate = int(vals[idx])
                if candidate not in used_prev_labels:
                    new_labels[mask] = candidate
                    used_prev_labels.add(candidate)
                    break
            else:
                new_labels[mask] = next_label_id
                next_label_id += 1
        else:
            # Entirely new cluster
            new_labels[mask] = next_label_id
            next_label_id += 1
            
    return new_labels, next_label_id

def get_animation_clustering(data: dict[str, Any], method: str, params: dict[str, Any], plane_step: int = 5) -> dict[str, Any]:
    """
    Calculates clustering for EVERY frame with temporal label stability.
    Uses global index matching for extreme performance.
    """
    # 1. Initialization & Pre-conversion
    lon, lat, dep = np.array(data['longitude']), np.array(data['latitude']), np.array(data['depth'])
    mags = np.array(data['magnitude'])
    dates_unique = data['visual_pack']['unique_dates']
    date_to_cum = data['visual_pack']['date_to_cum']
    anim_mode = params.get('anim_mode', data.get('anim_mode', 'accumulation'))
    window_days = int(params.get('window_days', data.get('window_days', 30)))
    step_days = int(params.get('step_days', data.get('step_days', 7)))
    
    if anim_mode == 'block':
        plane_step = 1
    
    origin_lat = data.get('origin_lat', np.mean(lat))
    origin_lon = data.get('origin_lon', np.mean(lon))
    pts_km = project_to_km(lon, lat, dep, origin_lat, origin_lon)

    # 2. Pre-calculate Temporal Windows
    dates_unique, date_indices = _get_frame_dates_and_indices(dates_unique, date_to_cum, anim_mode, window_days, step_days)

    # 3. Pre-calculate Grid if cylinders are used
    use_cylinders = params.get('use_cylinders', False)
    grid_info = []
    pt_cylinder_map = None # Spatial assignment optimization
    if use_cylinders:
        radius_km = float(params.get('cylinder_radius', 0.5))
        overlap = 0.2
        spacing = radius_km * (2.0 - overlap)
        min_x, max_x = np.min(pts_km[:, 0]), np.max(pts_km[:, 0])
        min_y, max_y = np.min(pts_km[:, 1]), np.max(pts_km[:, 1])
        grid_x = np.arange(min_x, max_x + spacing, spacing)
        grid_y = np.arange(min_y, max_y + spacing, spacing)
        
        centers = []
        for ix, cx in enumerate(grid_x):
            for iy, cy in enumerate(grid_y):
                grid_info.append((ix, iy, cx, cy))
                centers.append([cx, cy])
        
        if centers:
            grid_tree = KDTree(np.array(centers))
            # Pre-assign each point to its NEAREST cylinder center once
            dists, pt_cylinder_map = grid_tree.query(pts_km[:, :2], distance_upper_bound=radius_km)
            pt_cylinder_map[dists == np.inf] = -1 # Points too far from any cylinder

    # 4. Filter params
    f_min_mag, f_max_mag = float(params.get('mag_min', -10)), float(params.get('mag_max', 10))
    f_min_dep, f_max_dep = float(params.get('dep_min', -100)), float(params.get('dep_max', 1000))

    t0 = time.time()
    logger.info(f"Starting multi-process animated clustering ({len(dates_unique)} frames, method={method})...")

    # Helper for the parallel worker
    worker_data = {
        'pts_km': pts_km,
        'mags': mags,
        'dep': dep,
        'date_indices': date_indices,
        'pt_cylinder_map': pt_cylinder_map,
        'params': params,
        'method': method,
        'use_cylinders': use_cylinders,
        'f_mag': (f_min_mag, f_max_mag),
        'f_dep': (f_min_dep, f_max_dep),
        'plane_step': plane_step,
        'origin_lon': origin_lon,
        'origin_lat': origin_lat
    }

    # 5. Execute Clustering with adaptive parallel/sequential execution
    frame_results = [None] * len(date_indices)
    _init_clustering_worker(worker_data)
    try:
        if len(date_indices) <= 15 or len(pts_km) < 1500:
            for i in range(len(date_indices)):
                res = _process_frame_worker(i, worker_data)
                frame_results[res[0]] = res
        else:
            n_workers = min(os.cpu_count() or 4, 8)
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                futures = [executor.submit(_process_frame_worker, i, worker_data) for i in range(len(date_indices))]
                for future in as_completed(futures):
                    res = future.result()
                    frame_results[res[0]] = res
    finally:
        _worker_clustering_data.clear()

    # 6. Sequential Post-processing (Matching & Renaming Planes)
    results = {}
    global_labels_map = np.full(len(pts_km), -1, dtype=int)
    next_label_id, has_initialized_labels = 0, False
    last_valid_planes = []
    
    for i, res in enumerate(frame_results):
        date_str = dates_unique[i]
        _, labels, _, global_indices, mask, raw_len, frame_planes = res
        final_labels = np.full(raw_len, -1)

        if labels is None:
            results[date_str] = {'labels': final_labels.tolist(), 'planes': last_valid_planes}
            global_labels_map[global_indices] = -1
            continue

        # CYLINDER STABILITY: 
        # IDs are stable centers, bypass matching.
        if use_cylinders:
            matched_labels = labels
        elif has_initialized_labels:
            matched_labels, next_label_id = match_labels_globally(labels, global_indices, global_labels_map, next_label_id)
        else:
            matched_labels = labels
            # Ensure next_label_id is high enough to not collide with cylinder IDs if needed
            # but for consistency we just use the unique count
            next_label_id = int(np.max(labels) + 1) if (use_cylinders and len(labels)>0) else len(np.unique(labels[labels != -1]))
            has_initialized_labels = True

        global_labels_map[global_indices] = matched_labels
        final_labels[mask] = matched_labels

        if frame_planes:
            # RENAME planes with matched global labels
            # We need a map from local labels to matched labels for this frame
            local_to_global = {}
            unique_local = np.unique(labels[labels != -1])
            for l_id in unique_local:
                # Find first instance of local label and get its global counterpart
                first_idx = np.where(labels == l_id)[0][0]
                local_to_global[l_id] = int(matched_labels[first_idx])
            
            # Update grid_ids in planes
            last_valid_planes = []
            for p in frame_planes:
                # grid_id format: cluster_{lid}_TMP
                parts = p['grid_id'].split('_')
                local_lid = int(parts[1])
                global_lid = local_to_global.get(local_lid, -1)
                if global_lid != -1:
                    p['grid_id'] = f"cluster_{global_lid}_{date_str}"
                    last_valid_planes.append(p)
        
        results[date_str] = {
            'labels': final_labels.tolist(), 
            'planes': last_valid_planes,
            'indices': global_indices.tolist()
        }
            
    results['global_labels'] = global_labels_map.tolist()
    results['method'] = method
    results['params'] = params if params is not None else {}
    logger.info(f"Parallel clustering completed in {time.time() - t0:.2f}s")
    return results

def _get_frame_dates_and_indices(dates, date_to_cum, mode, window_days, step_days=7):
    if mode == 'accumulation':
        return dates, [(0, date_to_cum[d]) for d in dates]
    
    dt_objs = [datetime.strptime(d, '%Y-%m-%d') for d in dates]
    
    if mode == 'block':
        d0 = dt_objs[0]
        d_end = dt_objs[-1]
        total_days = (d_end - d0).days
        num_blocks = (total_days // step_days) + 1
        
        block_dates = []
        indices = []
        
        for b_i in range(num_blocks):
            start_cutoff = d0 + timedelta(days=b_i * step_days)
            end_cutoff = start_cutoff + timedelta(days=window_days)
            start_cutoff_str = start_cutoff.strftime('%Y-%m-%d')
            end_cutoff_str = end_cutoff.strftime('%Y-%m-%d')
            
            # Binary search: find the position of start and end cutoffs in O(log N)
            pos_s = bisect.bisect_left(dates, start_cutoff_str)
            s_idx = date_to_cum[dates[pos_s - 1]] if pos_s > 0 else 0
            
            pos_e = bisect.bisect_left(dates, end_cutoff_str)
            e_idx = date_to_cum[dates[pos_e - 1]] if pos_e > 0 else 0
            
            block_dates.append(start_cutoff_str)
            indices.append((s_idx, e_idx))
        return block_dates, indices
    
    indices = []
    for i, d_str in enumerate(dates):
        cutoff_str = (dt_objs[i] - timedelta(days=window_days - 1)).strftime('%Y-%m-%d')
        # Binary search: find first date >= cutoff in O(log N)
        j = bisect.bisect_left(dates, cutoff_str)
        s_idx = date_to_cum[dates[j - 1]] if j > 0 else 0
        indices.append((s_idx, date_to_cum[d_str]))
    return dates, indices

def compute_robust_hull_simplices(pts: np.ndarray) -> list[list[int]] | None:
    """
    Compute convex hull simplices in 3D.
    If 3D ConvexHull fails because points are coplanar or nearly coplanar
    (a common case for planar fault clusters), project onto the 2D plane of maximum
    variance via SVD and compute the 2D convex hull with fan triangulation.
    """
    if len(pts) < 3:
        return None
    try:
        hull_3d = ConvexHull(pts)
        return hull_3d.simplices.tolist()
    except Exception:
        try:
            centered = pts - np.mean(pts, axis=0)
            _, _, vh = svd(centered, full_matrices=False)
            pts_2d = centered @ vh[:2].T
            hull_2d = ConvexHull(pts_2d)
            v = hull_2d.vertices
            if len(v) >= 3:
                return [[int(v[0]), int(v[k]), int(v[k + 1])] for k in range(1, len(v) - 1)]
            return None
        except Exception:
            return None

def _calculate_frame_planes(labels, points, date_str, origin_lon, origin_lat):
    lon_to_km = KM_PER_DEGREE * np.cos(np.radians(origin_lat))
    planes = []
    unique_ids = [lid for lid in np.unique(labels) if lid != -1]
    
    for lid in unique_ids:
        mask = (labels == lid)
        cluster_pts = points[mask]
        if len(cluster_pts) < 4:
            continue
        
        # PERFORMANCE: Sample points if cluster is huge
        if len(cluster_pts) > 300:
            fit_pts = cluster_pts[np.random.choice(len(cluster_pts), 300, replace=False)]
        else:
            fit_pts = cluster_pts

        normal, centroid, planarity = fit_plane_ransac(fit_pts, threshold=0.15)
        if normal is not None and centroid is not None:
            c_lon = (centroid[0] / lon_to_km) + origin_lon
            c_lat = (centroid[1] / KM_PER_DEGREE) + origin_lat
            
            dists = np.linalg.norm(cluster_pts - centroid, axis=1)
            radius_eff = max(0.2, float(np.percentile(dists, 90)))
            
            p_data = _format_plane_geometry(
                normal, centroid, planarity, c_lon, c_lat, lon_to_km, radius_eff
            )
            p_data['grid_id'] = f"cluster_{lid}_{date_str}"
            
            simplices = compute_robust_hull_simplices(fit_pts)
            if simplices is not None:
                # Convert from km back to degrees for plotly
                hx = (fit_pts[:, 0] / lon_to_km) + origin_lon
                hy = (fit_pts[:, 1] / KM_PER_DEGREE) + origin_lat
                
                p_data['hull'] = {
                    'x': hx.tolist(),
                    'y': hy.tolist(),
                    'z': fit_pts[:, 2].tolist(),
                    'simplices': simplices
                }
            else:
                p_data['hull'] = None

            planes.append(p_data)
    return planes

def _perform_cylinder_clustering(curr_pt_cylinder_map):
    """Partitions points into cylinders."""
    n = len(curr_pt_cylinder_map)
    labels = np.full(n, -1, dtype=int)
    
    if n == 0:
        return labels, 0

    # VECTORIZED GROUPING: Avoid O(Cylinders * Points) loop
    sort_idx = np.argsort(curr_pt_cylinder_map)
    sorted_maps = curr_pt_cylinder_map[sort_idx]
    
    # Find where cylinder IDs change
    splits = np.where(np.diff(sorted_maps) != 0)[0] + 1
    
    idx_groups = np.split(sort_idx, splits)
    
    for i, g_idx in enumerate(idx_groups):
        if len(g_idx) < 5: # MIN THRESHOLD to avoid forced/ghost clusters
            continue
            
        cylinder_idx = sorted_maps[splits[i-1] if i > 0 else 0]
        if cylinder_idx == -1:
            continue
            
        # Just one cluster per cylinder
        labels[g_idx] = int(cylinder_idx)
            
    valid_labels = labels[labels != -1]
    return labels, len(np.unique(valid_labels)) if len(valid_labels) > 0 else 0

def _process_frame_worker(idx, data=None):
    """Worker function for ProcessPoolExecutor."""
    if data is None:
        data = _worker_clustering_data
    start_idx, end_idx = data['date_indices'][idx]
    pts_km = data['pts_km']
    mags = data['mags']
    dep = data['dep']
    pt_cylinder_map = data['pt_cylinder_map']
    params = data['params']
    method = data['method']
    use_cylinders = data['use_cylinders']
    f_mag = data['f_mag']
    f_dep = data['f_dep']
    plane_step = data['plane_step']
    origin_lon = data['origin_lon']
    origin_lat = data['origin_lat']

    pts_raw = pts_km[start_idx:end_idx]
    abs_dep = np.abs(dep[start_idx:end_idx])
    mask = (mags[start_idx:end_idx] >= f_mag[0]) & (mags[start_idx:end_idx] <= f_mag[1]) & \
           (abs_dep >= f_dep[0]) & (abs_dep <= f_dep[1])
    
    pts_subset = pts_raw[mask]
    global_indices = np.arange(start_idx, end_idx)[mask]
    
    if len(pts_subset) < 3:
        return idx, None, None, global_indices, mask, len(pts_raw), []

    if use_cylinders:
        curr_pt_cylinder_map = pt_cylinder_map[start_idx:end_idx][mask]
        depth_step = float(params.get('cylinder_depth_step', 0))
        
        if depth_step > 0:
            # Partition by depth as well
            depths = dep[start_idx:end_idx][mask]
            # Use floor division for stable vertical levels
            depth_idx = np.floor(np.abs(depths) / depth_step).astype(int)
            # Combine: (Cyl * 1000) + DepthLevel
            combined_map = (curr_pt_cylinder_map * 1000) + depth_idx
            # Restore -1 for points outside cylinders
            combined_map[curr_pt_cylinder_map == -1] = -1
        else:
            combined_map = curr_pt_cylinder_map

        labels, _ = _perform_cylinder_clustering(combined_map)
        centroids = None
    else:
        labels, _, centroids = perform_clustering(pts_subset, method, params, None)
        
    frame_planes = []
    if (idx % plane_step == 0) and labels is not None:
        frame_planes = _calculate_frame_planes(labels, pts_subset, "TMP", origin_lon, origin_lat)

    return idx, labels, centroids, global_indices, mask, len(pts_raw), frame_planes

def _find_elbow_point(x_vals: np.ndarray, y_vals: np.ndarray) -> int:
    """Find the elbow point index in a curve using maximum orthogonal distance to the start-end line."""
    if len(x_vals) == 0:
        return 0
    all_coord = np.vstack((x_vals, y_vals)).T
    first_point = all_coord[0]
    line_vec = all_coord[-1] - first_point
    norm_val = np.linalg.norm(line_vec)
    if norm_val <= 0:
        return 0
    line_vec_norm = line_vec / norm_val
    vec_from_first = all_coord - first_point
    scalar_proj = np.sum(vec_from_first * line_vec_norm, axis=1)
    vec_proj = np.outer(scalar_proj, line_vec_norm)
    vec_to_line = vec_from_first - vec_proj
    dist_to_line = np.linalg.norm(vec_to_line, axis=1)
    return int(np.argmax(dist_to_line))

def auto_tune_dbscan_params(target_lon: np.ndarray, target_lat: np.ndarray, target_dep: np.ndarray, data: dict[str, Any], clustering_params: dict[str, Any]) -> None:
    """Auto-tune DBSCAN min_samples and eps using k-nearest neighbors and elbow detection."""
    if len(target_lon) < 5:
        return
    try:
        # Exclude events with missing depth from 3D parameter tuning
        if 'depth_is_missing' in data and data['depth_is_missing'] is not None:
            dim = np.array(data['depth_is_missing'], dtype=bool)
            mask = ~dim if len(dim) == len(target_lon) else ~dim[:len(target_lon)]
            if np.sum(mask) >= 5:
                target_lon, target_lat, target_dep = target_lon[mask], target_lat[mask], target_dep[mask]

        o_lat = data.get('origin_lat', float(np.mean(target_lat)))
        o_lon = data.get('origin_lon', float(np.mean(target_lon)))
        
        pts_km = project_to_km(target_lon, target_lat, target_dep, o_lat, o_lon)
        n_pts = len(pts_km)
        
        optimal_min_samples = max(3, int(np.log(n_pts))) if n_pts > 0 else 3
        clustering_params['dbscan_min_samples'] = optimal_min_samples
        min_samples = optimal_min_samples
        
        if len(pts_km) > min_samples:
            nn = NearestNeighbors(n_neighbors=min_samples)
            nn.fit(pts_km)
            distances, _ = nn.kneighbors(pts_km)
            
            k_dists = np.sort(distances[:, -1])
            if len(k_dists) > 0:
                elbow_idx = _find_elbow_point(np.arange(len(k_dists)), k_dists)
                optimal_eps_km = k_dists[elbow_idx]
                
                optimal_eps_m = max(10, int(round((optimal_eps_km * 1000) / 10.0) * 10))
                clustering_params['dbscan_eps'] = optimal_eps_m

        if 'dates_num' in data and data['dates_num'] is not None:
            auto_tune_time_window(data['dates_num'][:len(target_lon)], clustering_params, min_samples=optimal_min_samples)
    except (ValueError, RuntimeError, TypeError, KeyError) as e:
        logger.warning(f"Failed to calculate optimal eps: {e}")

def auto_tune_kmeans_params(target_lon: np.ndarray, target_lat: np.ndarray, target_dep: np.ndarray, data: dict[str, Any], clustering_params: dict[str, Any]) -> None:
    """Auto-tune KMeans k using inertia curve and elbow detection."""
    if len(target_lon) < 3:
        return
    try:
        # Exclude events with missing depth from 3D parameter tuning
        if 'depth_is_missing' in data and data['depth_is_missing'] is not None:
            dim = np.array(data['depth_is_missing'], dtype=bool)
            mask = ~dim if len(dim) == len(target_lon) else ~dim[:len(target_lon)]
            if np.sum(mask) >= 3:
                target_lon, target_lat, target_dep = target_lon[mask], target_lat[mask], target_dep[mask]

        o_lat = data.get('origin_lat', float(np.mean(target_lat)))
        o_lon = data.get('origin_lon', float(np.mean(target_lon)))

        pts_km = project_to_km(target_lon, target_lat, target_dep, o_lat, o_lon)
        n_pts = len(pts_km)
        max_k = min(10, n_pts)
        if max_k < 3:
            return

        ks = list(range(2, max_k + 1))
        inertias = []
        for k in ks:
            km = MiniBatchKMeans(n_clusters=k, random_state=42, n_init='auto').fit(pts_km)
            inertias.append(float(km.inertia_))

        if len(ks) > 0:
            elbow_idx = _find_elbow_point(np.array(ks), np.array(inertias))
            optimal_k = ks[elbow_idx]
            clustering_params['kmeans_clusters'] = int(optimal_k)

        if 'dates_num' in data and data['dates_num'] is not None:
            auto_tune_time_window(data['dates_num'][:len(target_lon)], clustering_params, min_samples=5)
    except (ValueError, RuntimeError, TypeError, KeyError) as e:
        logger.warning(f"Failed to calculate optimal kmeans clusters: {e}")

def auto_tune_hdbscan_params(target_lon: np.ndarray, target_lat: np.ndarray, target_dep: np.ndarray, data: dict[str, Any], clustering_params: dict[str, Any]) -> None:
    """Auto-tune HDBSCAN min_cluster_size, min_samples and optimal cluster_selection_epsilon using k-nearest neighbors and elbow detection."""
    if len(target_lon) < 5:
        return
    try:
        # Exclude events with missing depth from 3D parameter tuning
        if 'depth_is_missing' in data and data['depth_is_missing'] is not None:
            dim = np.array(data['depth_is_missing'], dtype=bool)
            mask = ~dim if len(dim) == len(target_lon) else ~dim[:len(target_lon)]
            if np.sum(mask) >= 5:
                target_lon, target_lat, target_dep = target_lon[mask], target_lat[mask], target_dep[mask]

        o_lat = data.get('origin_lat', float(np.mean(target_lat)))
        o_lon = data.get('origin_lon', float(np.mean(target_lon)))

        pts_km = project_to_km(target_lon, target_lat, target_dep, o_lat, o_lon)
        n_pts = len(pts_km)

        # In seismology, swarms typically have >= 4-10 events.
        # min_samples regulates noise sensitivity (core distance):
        optimal_min_samples = max(3, min(15, int(np.log(n_pts)))) if n_pts > 0 else 3
        # min_cluster_size sets the smallest viable geological fault patch:
        optimal_min_cluster_size = max(5, int(round(optimal_min_samples * 1.5)))
        clustering_params['hdbscan_min_cluster_size'] = optimal_min_cluster_size
        clustering_params['hdbscan_min_samples'] = optimal_min_samples

        if len(pts_km) > optimal_min_samples:
            nn = NearestNeighbors(n_neighbors=optimal_min_samples)
            nn.fit(pts_km)
            distances, _ = nn.kneighbors(pts_km)

            k_dists = np.sort(distances[:, -1])
            if len(k_dists) > 0:
                elbow_idx = _find_elbow_point(np.arange(len(k_dists)), k_dists)
                optimal_eps_km = k_dists[elbow_idx]
                # Clamp within reasonable physical seismological bounds (20m to 2000m)
                optimal_eps_m = max(20, min(2000, int(round((optimal_eps_km * 1000) / 10.0) * 10)))
                clustering_params['hdbscan_cluster_selection_epsilon'] = optimal_eps_m
                clustering_params['hdbscan_eps'] = optimal_eps_m

        if 'dates_num' in data and data['dates_num'] is not None:
            auto_tune_time_window(data['dates_num'][:len(target_lon)], clustering_params, min_samples=optimal_min_samples)
    except (ValueError, RuntimeError, TypeError, KeyError) as e:
        logger.warning(f"Failed to calculate optimal hdbscan params: {e}")

def auto_tune_time_window(dates_num: np.ndarray | list[float], clustering_params: dict[str, Any], min_samples: int = 5) -> float:
    """
    Auto-tune the spatio-temporal correlation time window (in hours / days) using temporal k-NN elbow detection.
    Finds the characteristic transition between rapid intra-swarm clustering and background recurrence intervals.
    Returns: optimal window in hours.
    """
    if dates_num is None or len(dates_num) < min_samples:
        clustering_params.setdefault('time_window_hours', 72.0)
        clustering_params.setdefault('time_window', 72.0)
        clustering_params.setdefault('time_window_days', 3.0)
        return 72.0
    try:
        t_arr = np.sort(np.asarray(dates_num, dtype=float))
        k = max(2, min(min_samples, len(t_arr) - 1))
        nn = NearestNeighbors(n_neighbors=k)
        nn.fit(t_arr.reshape(-1, 1))
        distances, _ = nn.kneighbors(t_arr.reshape(-1, 1))
        k_dists = np.sort(distances[:, -1])
        if len(k_dists) > 0:
            elbow_idx = _find_elbow_point(np.arange(len(k_dists)), k_dists)
            optimal_window_days = float(k_dists[elbow_idx])
            # Clamp between 0.05 days (1.2h) and 60.0 days (1440h) for realistic seismological swarms
            optimal_window_days = max(0.05, min(60.0, optimal_window_days))
            optimal_window_hours = max(1.0, min(1440.0, round(optimal_window_days * 24.0, 1)))
            clustering_params['time_window_hours'] = optimal_window_hours
            clustering_params['time_window'] = optimal_window_hours
            clustering_params['time_window_days'] = round(optimal_window_hours / 24.0, 2)
            return optimal_window_hours
    except Exception as e:
        logger.warning(f"Failed to calculate optimal time window: {e}")
    clustering_params.setdefault('time_window_hours', 72.0)
    clustering_params.setdefault('time_window', 72.0)
    clustering_params.setdefault('time_window_days', 3.0)
    return 72.0
