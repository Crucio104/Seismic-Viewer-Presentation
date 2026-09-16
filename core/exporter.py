import csv
import io
import json
import logging
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def get_cluster_header_comment(method: str, params: Any) -> str:
    """Format clustering metadata comment line."""
    if isinstance(params, dict):
        m = str(method).lower()
        if m == 'dbscan':
            eps = params.get('dbscan_eps') or params.get('eps') or params.get('eps_km', 'N/A')
            min_samp = params.get('dbscan_min_samples') or params.get('min_samples', 'N/A')
            param_str = f"eps={eps}, min_samples={min_samp}"
        elif m == 'hdbscan':
            min_size = params.get('hdbscan_min_cluster_size') or params.get('min_cluster_size', 'N/A')
            min_samp = params.get('hdbscan_min_samples') or params.get('min_samples', 'N/A')
            eps = params.get('hdbscan_cluster_selection_epsilon') or params.get('cluster_selection_epsilon') or params.get('hdbscan_eps', 0)
            param_str = f"min_cluster_size={min_size}, min_samples={min_samp}, cluster_selection_epsilon={eps}m"
        elif m == 'kmeans':
            n_clust = params.get('kmeans_clusters') or params.get('n_clusters') or params.get('kmeans_n_clusters', 'N/A')
            max_d = params.get('kmeans_max_dist')
            if max_d and float(max_d) > 0:
                param_str = f"n_clusters={n_clust}, max_dist_m={max_d}"
            else:
                param_str = f"n_clusters={n_clust}"
        else:
            param_str = ", ".join(f"{k}={v}" for k, v in params.items())

        if params.get('use_time'):
            time_win_h = params.get('time_window_hours')
            if time_win_h is None and 'time_window' in params:
                time_win_h = params.get('time_window')
            if time_win_h is not None:
                param_str += f", spatio_temporal=True, time_window={time_win_h}h"
            else:
                time_win_d = params.get('time_window_days', 'N/A')
                param_str += f", spatio_temporal=True, time_window={time_win_d}d"
        else:
            param_str += ", spatio_temporal=False"
    else:
        param_str = str(params)
    return f"# Clustering Method: {str(method).upper()} | Parameters: {param_str}\n"


def build_cluster_csv_text(data: dict[str, Any] | None, idx_list: list[int], header_comment: str) -> str:
    """Generate formatted CSV text for a list of event indices."""
    times = data.get('times', []) if data else []
    lats = data.get('latitude', []) if data else []
    lons = data.get('longitude', []) if data else []
    deps = data.get('depth', []) if data else []
    mags = data.get('magnitude', []) if data else []
    n_events = len(lons)

    valid_indices = [int(i) for i in idx_list if 0 <= int(i) < n_events]
    output = io.StringIO()
    output.write(header_comment)
    writer = csv.writer(output)
    writer.writerow(['time', 'latitude', 'longitude', 'depth', 'magnitude'])
    for i in valid_indices:
        writer.writerow([
            times[i] if i < len(times) else '',
            f"{float(lats[i]):.6f}",
            f"{float(lons[i]):.6f}",
            f"{abs(float(deps[i])):.4f}" if i < len(deps) else "0.0",
            f"{float(mags[i]):.2f}" if i < len(mags) else "0.0"
        ])
    return output.getvalue()


def build_cluster_geojson_text(data: dict[str, Any] | None, idx_list: list[int], method: str, params: Any, cluster_name: str = "cluster") -> str:
    """Generate RFC 7946 compliant GeoJSON text for a cluster of earthquake events."""
    times = data.get('times', []) if data else []
    lats = data.get('latitude', []) if data else []
    lons = data.get('longitude', []) if data else []
    deps = data.get('depth', []) if data else []
    mags = data.get('magnitude', []) if data else []
    n_events = len(lons)

    valid_indices = [int(i) for i in idx_list if 0 <= int(i) < n_events]
    features = []
    for i in valid_indices:
        lon = float(lons[i])
        lat = float(lats[i])
        depth = abs(float(deps[i])) if i < len(deps) else 0.0
        elevation_m = -depth * 1000.0  # Depth below sea level in meters

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(lon, 6), round(lat, 6), round(elevation_m, 1)]
            },
            "properties": {
                "event_index": i,
                "time": str(times[i]) if i < len(times) else "",
                "magnitude": round(float(mags[i]), 2) if i < len(mags) else 0.0,
                "depth_km": round(depth, 4),
                "cluster": cluster_name
            }
        })

    geojson_obj = {
        "type": "FeatureCollection",
        "name": cluster_name,
        "crs": {
            "type": "name",
            "properties": {
                "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
            }
        },
        "metadata": {
            "clustering_method": str(method).upper(),
            "clustering_parameters": params if isinstance(params, dict) else str(params),
            "total_events": len(features)
        },
        "features": features
    }
    return json.dumps(geojson_obj, indent=2)


def _cluster_filename(label: int | str) -> str:
    """Format standard export filename for a cluster label."""
    lbl_int = int(label)
    return "outliers.csv" if lbl_int == -1 else f"cluster_{lbl_int}.csv"


def collect_cluster_export_items(payload: dict[str, Any] | None, last_result: dict[str, Any] | None = None) -> tuple[str, Any, list[tuple[str, list[int]]]]:
    """Extract method, params, and (filename, indices) tuples from export payload."""
    payload = payload or {}
    method = payload.get('method', 'dbscan')
    params = payload.get('params', {})
    export_items: list[tuple[str, list[int]]] = []

    if payload.get('clusters'):
        for item in payload['clusters']:
            fname = item.get('filename')
            idxs = item.get('indices', [])
            if fname and idxs:
                export_items.append((fname, idxs))
    elif payload.get('cluster_indices'):
        for lbl_str, idx_list in payload['cluster_indices'].items():
            if idx_list:
                export_items.append((_cluster_filename(lbl_str), idx_list))
    elif last_result:
        method = last_result.get('method', method)
        params = last_result.get('params', params)
        c_indices = last_result.get('cluster_indices')
        if c_indices:
            for lbl_str, idx_list in c_indices.items():
                if idx_list:
                    export_items.append((_cluster_filename(lbl_str), idx_list))
        elif last_result.get('labels') is not None:
            c_map = defaultdict(list)
            for idx, lbl in enumerate(last_result['labels']):
                c_map[int(lbl)].append(idx)
            for lbl_int, idx_list in c_map.items():
                if idx_list:
                    export_items.append((_cluster_filename(lbl_int), idx_list))
    return method, params, export_items


def write_single_cluster_csv(data: dict[str, Any] | None, save_path: Path, idx_list: list[int], method: str, params: Any) -> None:
    """Write a single cluster CSV to the designated path."""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    header_comment = get_cluster_header_comment(method, params)
    csv_text = build_cluster_csv_text(data, idx_list, header_comment)
    with open(save_path, 'w', encoding='utf-8', newline='') as f:
        f.write(csv_text)


def write_single_cluster_geojson(data: dict[str, Any] | None, save_path: Path, idx_list: list[int], method: str, params: Any, cluster_name: str = "cluster") -> None:
    """Write a single cluster GeoJSON to the designated path."""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    geojson_text = build_cluster_geojson_text(data, idx_list, method, params, cluster_name)
    with open(save_path, 'w', encoding='utf-8') as f:
        f.write(geojson_text)


def write_clusters_zip(data: dict[str, Any] | None, save_path: Path, export_items: list[tuple[str, list[int]]], method: str, params: Any, file_format: str = "csv") -> int:
    """Write multiple cluster files (CSV or GeoJSON) into a compressed ZIP archive. Returns the number of exported clusters."""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    header_comment = get_cluster_header_comment(method, params)
    exported_count = 0
    is_geojson = str(file_format).lower() == 'geojson'

    with zipfile.ZipFile(save_path, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, idx_list in export_items:
            base_stem = Path(file_name).stem
            if is_geojson:
                entry_name = f"{base_stem}.geojson"
                content = build_cluster_geojson_text(data, idx_list, method, params, cluster_name=base_stem)
            else:
                entry_name = f"{base_stem}.csv"
                content = build_cluster_csv_text(data, idx_list, header_comment)
            zip_file.writestr(entry_name, content)
            exported_count += 1
    return exported_count
