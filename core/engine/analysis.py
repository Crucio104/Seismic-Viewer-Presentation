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
    best_loss = float('inf')
    
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
        
        # Loss function: radice del quadrato della distanza media dal piano dei punti
        loss = np.sqrt(np.mean(dists)**2)
        
        inliers = np.where(dists < threshold)[0]
        if len(inliers) >= min_inliers and loss < best_loss:
            best_loss = loss
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

def get_animation_planes(data: dict[str, Any], radius_km: float, min_pts: int, window_days: int, anim_mode: str = 'accumulation') -> dict[str, list[dict[str, Any]]]:
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
    
    # Get frame indices using the same logic as clustering
    date_indices = _get_frame_indices(dates_unique, date_to_cum, anim_mode, window_days)
    
    for i, date_str in enumerate(dates_unique):
        start_idx, end_idx = date_indices[i]
        
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

def perform_clustering(pts_km: np.ndarray, method: str = 'dbscan', params: dict[str, Any] | None = None, prev_centroids: np.ndarray | None = None) -> tuple[np.ndarray, int, np.ndarray | None]:
    """
    Perform clustering (KMeans or DBSCAN) on 3D points.
    Returns: (labels, n_clusters, centroids)
    """
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
                    dists = np.linalg.norm(pts - centroid_km, axis=1)
                    radius_eff = max(0.2, float(np.percentile(dists, 90)))
                    
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
    window_days = int(params.get('window_days', data.get('window_days', 5)))
    
    origin_lat = data.get('origin_lat', np.mean(lat))
    origin_lon = data.get('origin_lon', np.mean(lon))
    pts_km = project_to_km(lon, lat, dep, origin_lat, origin_lon)

    # 2. Pre-calculate Temporal Windows
    date_indices = _get_frame_indices(dates_unique, date_to_cum, anim_mode, window_days)

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

    import time
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

    # Use max_workers to avoid saturating everything and allowing some room for the server
    n_workers = min(os.cpu_count(), 8)
    
    # 5. Execute Parallel Clustering
    frame_results = [None] * len(date_indices)
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        # Submit in chunks if frames are many
        futures = [executor.submit(_process_frame_worker, i, worker_data) for i in range(len(date_indices))]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            frame_results[res[0]] = res

    # 6. Sequential Post-processing (Matching & Renaming Planes)
    results = {}
    global_labels_map = np.full(len(pts_km), -1, dtype=int)
    next_label_id, has_initialized_labels = 0, False
    last_valid_planes = []
    
    for i, res in enumerate(frame_results):
        date_str = dates_unique[i]
        idx, labels, centroids, global_indices, mask, raw_len, frame_planes = res
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
            
    logger.info(f"Parallel clustering completed in {time.time() - t0:.2f}s")
    return results

def _get_frame_indices(dates, date_to_cum, mode, window_days):
    indices = []
    if mode == 'accumulation':
        return [(0, date_to_cum[d]) for d in dates]
    
    from datetime import datetime, timedelta
    dt_objs = [datetime.strptime(d, '%Y-%m-%d') for d in dates]
    
    if mode == 'block':
        d0 = dt_objs[0]
        for i, d_str in enumerate(dates):
            t_i = (dt_objs[i] - d0).days
            b_i = t_i // window_days
            cutoff = d0 + timedelta(days=b_i * window_days)
            cutoff_str = cutoff.strftime('%Y-%m-%d')
            s_idx = 0
            for j, d in enumerate(dates):
                if d >= cutoff_str:
                    s_idx = date_to_cum[dates[j-1]] if j > 0 else 0
                    break
            indices.append((s_idx, date_to_cum[d_str]))
        return indices
    
    for i, d_str in enumerate(dates):
        cutoff = dt_objs[i] - timedelta(days=window_days-1)
        s_idx = 0
        for j, d in enumerate(dates):
            if d >= cutoff.strftime('%Y-%m-%d'):
                s_idx = date_to_cum[dates[j-1]] if j > 0 else 0
                break
        indices.append((s_idx, date_to_cum[d_str]))
    return indices

def _calculate_frame_planes(labels, points, date_str, origin_lon, origin_lat, dim):
    from core.config import KM_PER_DEGREE
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
            planes.append(p_data)
    return planes

def _perform_cylinder_clustering(pts_subset, curr_pt_cylinder_map, method, params):
    """Partitions points into cylinders."""
    labels = np.full(len(pts_subset), -1, dtype=int)
    
    if len(pts_subset) == 0:
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

def _process_frame_worker(idx, data):
    """Worker function for ProcessPoolExecutor."""
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
        else:
            combined_map = curr_pt_cylinder_map

        labels, n_clusters = _perform_cylinder_clustering(pts_subset, combined_map, method, params)
        centroids = None
    else:
        labels, n_clusters, centroids = perform_clustering(pts_subset, method, params, None)
        
    frame_planes = []
    if (idx % plane_step == 0) and labels is not None:
        frame_planes = _calculate_frame_planes(labels, pts_subset, "TMP", origin_lon, origin_lat, pts_km.shape[1])

    return idx, labels, centroids, global_indices, mask, len(pts_raw), frame_planes
