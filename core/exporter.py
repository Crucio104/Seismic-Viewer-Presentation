import csv
import io
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
        elif m == 'kmeans':
            n_clust = params.get('kmeans_clusters') or params.get('n_clusters') or params.get('kmeans_n_clusters', 'N/A')
            max_d = params.get('kmeans_max_dist')
            if max_d and float(max_d) > 0:
                param_str = f"n_clusters={n_clust}, max_dist_m={max_d}"
            else:
                param_str = f"n_clusters={n_clust}"
        else:
            param_str = ", ".join(f"{k}={v}" for k, v in params.items())
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
            lbl_int = int(lbl_str)
            fname = "outliers.csv" if lbl_int == -1 else f"cluster_{lbl_int}.csv"
            if idx_list:
                export_items.append((fname, idx_list))
    elif last_result:
        method = last_result.get('method', method)
        params = last_result.get('params', params)
        c_indices = last_result.get('cluster_indices')
        if c_indices:
            for lbl_str, idx_list in c_indices.items():
                lbl_int = int(lbl_str)
                fname = "outliers.csv" if lbl_int == -1 else f"cluster_{lbl_int}.csv"
                if idx_list:
                    export_items.append((fname, idx_list))
        elif last_result.get('labels') is not None:
            c_map = defaultdict(list)
            for idx, lbl in enumerate(last_result['labels']):
                c_map[int(lbl)].append(idx)
            for lbl_int, idx_list in c_map.items():
                fname = "outliers.csv" if lbl_int == -1 else f"cluster_{lbl_int}.csv"
                if idx_list:
                    export_items.append((fname, idx_list))
    return method, params, export_items


def write_single_cluster_csv(data: dict[str, Any] | None, save_path: Path, idx_list: list[int], method: str, params: Any) -> None:
    """Write a single cluster CSV to the designated path."""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    header_comment = get_cluster_header_comment(method, params)
    csv_text = build_cluster_csv_text(data, idx_list, header_comment)
    with open(save_path, 'w', encoding='utf-8', newline='') as f:
        f.write(csv_text)


def write_clusters_zip(data: dict[str, Any] | None, save_path: Path, export_items: list[tuple[str, list[int]]], method: str, params: Any) -> int:
    """Write multiple cluster CSV files into a compressed ZIP archive. Returns the number of exported clusters."""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    header_comment = get_cluster_header_comment(method, params)
    exported_count = 0
    with zipfile.ZipFile(save_path, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, idx_list in export_items:
            csv_text = build_cluster_csv_text(data, idx_list, header_comment)
            zip_file.writestr(file_name, csv_text)
            exported_count += 1
    return exported_count
