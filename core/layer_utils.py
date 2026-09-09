import logging
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from core.config import BASE_DIR

logger = logging.getLogger(__name__)

def utm33_to_latlon_numpy(x_km: np.ndarray | float, y_km: np.ndarray | float) -> tuple[np.ndarray | float, np.ndarray | float]:
    """
    Convert UTM Zone 33N coordinates (in km) to WGS84 Latitude and Longitude (in degrees).
    Uses standard Transverse Mercator projection equations on WGS84 ellipsoid.
    """
    x = np.asarray(x_km, dtype=np.float64) * 1000.0 - 500000.0
    y = np.asarray(y_km, dtype=np.float64) * 1000.0
    
    a = 6378137.0
    e = 0.08181919104281579
    k0 = 0.9996
    e1sq = 0.006739496742276434
    
    M = y / k0
    mu = M / (a * (1 - e**2/4 - 3*e**4/64 - 5*e**6/256))
    e1 = (1 - (1 - e**2)**0.5) / (1 + (1 - e**2)**0.5)
    
    phi1 = mu + (3*e1/2 - 27*e1**3/32)*np.sin(2*mu) + (21*e1**2/16 - 55*e1**4/32)*np.sin(4*mu) + (151*e1**3/96)*np.sin(6*mu) + (1097*e1**4/512)*np.sin(8*mu)
    
    C1 = e1sq * np.cos(phi1)**2
    T1 = np.tan(phi1)**2
    N1 = a / (1 - (e * np.sin(phi1))**2)**0.5
    R1 = a * (1 - e**2) / (1 - (e * np.sin(phi1))**2)**1.5
    D = x / (N1 * k0)
    
    lat = phi1 - (N1 * np.tan(phi1) / R1) * (
        D**2/2 - (5 + 3*T1 + 10*C1 - 4*C1**2 - 9*e1sq)*D**4/24 + 
        (61 + 90*T1 + 298*C1 + 45*T1**2 - 252*e1sq - 3*C1**2)*D**6/720
    )
    lon = np.radians(15.0) + (
        D - (1 + 2*T1 + C1)*D**3/6 + 
        (5 - 2*C1 + 28*T1 - 3*C1**2 + 8*e1sq + 24*T1**2)*D**5/120
    ) / np.cos(phi1)
    
    if isinstance(x_km, (int, float)):
        return float(np.degrees(lat)), float(np.degrees(lon))
    return np.degrees(lat), np.degrees(lon)


def _read_csv_flexible(path: Path | str) -> pd.DataFrame:
    """Helper to read CSV with flexible separator and C-engine speed, with fallback to Python engine."""
    p = Path(path)
    try:
        df = pd.read_csv(p, sep=';', encoding='utf-8', engine='c')
        if len(df.columns) <= 1:
            df = pd.read_csv(p, sep=',', encoding='utf-8', engine='c')
        return df
    except Exception:
        return pd.read_csv(p, sep=None, engine='python')


def process_tomography_data(csv_path: str | Path) -> dict[str, Any]:
    """Read tomography CSV, convert UTM coordinates, and extract Vp/Vs ratio."""
    try:
        path = Path(csv_path)
        if not path.exists():
            return {'error': f"File not found: {csv_path}"}
        
        df = _read_csv_flexible(path)
            
        # Clean column names
        df.columns = [c.strip().upper() for c in df.columns]
        
        # Find required columns
        utmx_col = next((c for c in df.columns if 'UTMX' in c or 'X' == c), None)
        utmy_col = next((c for c in df.columns if 'UTMY' in c or 'Y' == c), None)
        utmz_col = next((c for c in df.columns if 'UTMZ' in c or 'Z' == c or 'DEPTH' in c), None)
        vpvs_col = next((c for c in df.columns if 'VP/VS' in c or 'VPXVS' in c or 'VPVS' in c or 'VP_VS' in c), None)
        
        if not all([utmx_col, utmy_col, utmz_col, vpvs_col]):
            return {'error': f"Missing columns in tomography CSV. Found: {list(df.columns)}"}
            
        # Drop NaN or invalid rows
        df = df.dropna(subset=[utmx_col, utmy_col, utmz_col, vpvs_col]).reset_index(drop=True)
        
        # Convert UTM Zone 33N km to Lat/Lon
        lats, lons = utm33_to_latlon_numpy(df[utmx_col].values, df[utmy_col].values)
        
        # In our 3D plot, Z is depth in km (positive downwards is represented as negative Z coordinates in 3D space)
        depths = -np.abs(df[utmz_col].values.astype(np.float32))
        vp_vs = df[vpvs_col].values.astype(np.float32)
        count_rows = len(df)
        
        # Only interpolate calibrated points (VP != 0) for clean volumes
        vp_col = next((c for c in df.columns if c == 'VP' or 'V_P' in c or 'P_VEL' in c), None)
        if vp_col is not None:
            mask = (df[vp_col].values != 0) & np.isfinite(vp_vs)
        else:
            mask = np.isfinite(vp_vs)
            
        # Free heavy pandas DataFrame immediately
        del df

        logger.info(f"Processed {count_rows} tomography points from {path.name}")
        
        # Build a regular 3D grid for volumetric rendering (server-side continuous IDW interpolation)
        iso_grid = None
        try:
            from scipy.spatial import cKDTree
            
            cal_lons = lons[mask]
            cal_lats = lats[mask]
            cal_depths = depths[mask]  # Already -abs(utmz)
            cal_vpvs = vp_vs[mask]
            
            if len(cal_vpvs) > 0:
                pts = np.column_stack([cal_lons, cal_lats, cal_depths])
                
                # Normalize coordinates to [0, 1] so horizontal (lat/lon) and vertical (depth) distances are isotropic
                coord_min = pts.min(axis=0)
                coord_ptp = np.maximum(pts.max(axis=0) - coord_min, 1e-9)
                pts_norm = (pts - coord_min) / coord_ptp
                
                tree = cKDTree(pts_norm)
                
                # Regular grid dimensions (optimized resolution for smooth 3D volumetric rendering with low memory footprint)
                nx, ny, nz = 30, 22, 16
                
                lon_min, lon_max = float(cal_lons.min()), float(cal_lons.max())
                lat_min, lat_max = float(cal_lats.min()), float(cal_lats.max())
                dep_min, dep_max = float(cal_depths.min()), float(cal_depths.max())
                
                X, Y, Z = np.mgrid[
                    lon_min:lon_max:nx*1j,
                    lat_min:lat_max:ny*1j,
                    dep_min:dep_max:nz*1j
                ]
                
                grid_pts = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
                grid_norm = (grid_pts - coord_min) / coord_ptp
                
                # Query k=16 nearest neighbors for smooth Inverse Distance Weighting (IDW)
                k_neighbors = min(16, len(cal_vpvs))
                dists, idxs = tree.query(grid_norm, k=k_neighbors)
                
                if dists.ndim == 1:
                    dists = dists[:, np.newaxis]
                    idxs = idxs[:, np.newaxis]
                
                # Avoid division by zero for points that coincide with sample locations
                eps = 1e-9
                dists = np.maximum(dists, eps)
                
                # Smooth Inverse Distance Weighting (power p = 2.0)
                weights = 1.0 / (dists ** 2.0)
                weights_sum = np.sum(weights, axis=1, keepdims=True)
                idw_vals = (np.sum(weights * cal_vpvs[idxs], axis=1, keepdims=True) / weights_sum).ravel()
                
                # Apply smooth Gaussian damping towards crustal background Vp/Vs (1.75) away from measured stations
                d_min = dists[:, 0]  # Distance to closest seismic sample
                sigma = 0.15         # Characteristic decay radius in normalized coordinates (~15% of bounding box)
                alpha = np.exp(-((d_min / sigma) ** 2))
                bg_val = 1.75
                flat_vals = alpha * idw_vals + (1.0 - alpha) * bg_val
                
                iso_grid = {
                    'x': np.round(X.flatten(), 4).tolist(),
                    'y': np.round(Y.flatten(), 4).tolist(),
                    'z': np.round(Z.flatten(), 2).tolist(),
                    'value': np.round(flat_vals, 3).tolist(),
                    'min_val': float(np.nanmin(flat_vals)),
                    'max_val': float(np.nanmax(flat_vals)),
                    'mean_val': float(np.nanmean(flat_vals)),
                }
                # Free numpy grid matrices
                del tree, pts, pts_norm, grid_pts, grid_norm, dists, idxs, weights, idw_vals, flat_vals, X, Y, Z
                logger.info(f"Generated 3D volume grid with continuous IDW: {nx}x{ny}x{nz} = {nx*ny*nz} voxels, "
                            f"Vp/Vs range [{iso_grid['min_val']:.3f}, {iso_grid['max_val']:.3f}]")
        except ImportError:
            logger.warning("scipy not available, 3D volume disabled")
        except Exception as e_iso:
            logger.warning(f"Error generating volume grid: {e_iso}")
        
        result = {
            'status': 'success',
            'type': 'tomography',
            'filename': path.name,
            'count': count_rows,
            'x': np.round(lons, 5).tolist(),
            'y': np.round(lats, 5).tolist(),
            'z': np.round(depths, 3).tolist(),
            'vp_vs': np.round(vp_vs, 3).tolist(),
            'min_vp_vs': float(np.min(vp_vs)),
            'max_vp_vs': float(np.max(vp_vs))
        }
        if iso_grid:
            result['iso_grid'] = iso_grid
        return result
    except Exception as e:
        logger.error(f"Error during tomography processing: {e}", exc_info=True)
        return {'error': f"Tomography processing error: {str(e)}"}


def process_uplift_data(csv_path: str | Path, target_date_str: str | None = None, stations_path: str | Path | None = None) -> dict[str, Any]:
    """Read GNSS uplift CSV, match station coordinates, and extract latest/closest uplift values."""
    try:
        path = Path(csv_path)
        if not path.exists():
            return {'error': f"File not found: {csv_path}"}
            
        df = _read_csv_flexible(path)
            
        df.columns = [c.strip().lower() for c in df.columns]
        
        station_col = next((c for c in df.columns if 'station' in c or 'staz' in c or 'id' == c), None)
        up_col = next((c for c in df.columns if 'up_m' in c or 'up' == c or 'height' in c or 'quota' in c), None)
        date_col = next((c for c in df.columns if 'date' in c or 'data' in c or 'time' in c), None)
        
        if not station_col or not up_col:
            return {'error': f"Missing columns 'station' or 'up_m' in uplift CSV. Found: {list(df.columns)}"}
            
        # Parse dates if date column exists
        if date_col:
            df['parsed_date'] = pd.to_datetime(df[date_col], format='%d/%m/%Y', errors='coerce')
            if df['parsed_date'].isna().all():
                df['parsed_date'] = pd.to_datetime(df[date_col], errors='coerce')
        
        # Load station coordinates mapping
        coord_map = _load_station_coordinates(path.parent, stations_path=stations_path)
        if not coord_map:
            return {'error': "Unable to locate station coordinates file (flegrei_station_coordinates.csv)"}
            
        # Filter stations present in coordinate map
        df = df[df[station_col].str.upper().isin(coord_map.keys())].copy()
        if len(df) == 0:
            return {'error': "No matching stations found in the coordinates file."}
            
        stations = []
        lons = []
        lats = []
        up_m_list = []
        dates_used = []
        
        # Group by station to find latest or target date
        for st_name, group in df.groupby(station_col):
            st_name = str(st_name).strip().upper()
            if st_name not in coord_map:
                continue
            lat, lon = coord_map[st_name]
            
            if date_col and 'parsed_date' in group.columns and not group['parsed_date'].isna().all():
                valid_group = group.dropna(subset=['parsed_date'])
                if target_date_str:
                    try:
                        t_date = pd.to_datetime(target_date_str)
                        idx = (valid_group['parsed_date'] - t_date).abs().idxmin()
                        row = valid_group.loc[idx]
                    except Exception:
                        row = valid_group.sort_values('parsed_date').iloc[-1]
                else:
                    row = valid_group.sort_values('parsed_date').iloc[-1]
                dt_str = row['parsed_date'].strftime('%Y-%m-%d')
            else:
                row = group.iloc[-1]
                dt_str = str(row[date_col]) if date_col in row else "Latest"
                
            up_val = float(row[up_col])
            
            stations.append(st_name)
            lons.append(lon)
            lats.append(lat)
            up_m_list.append(up_val)
            dates_used.append(dt_str)
            
        # Visual scaling factor: scale uplift meters so that columns rise cleanly above z=0 plane
        # Since differences between stations can be just a few millimeters, we scale the variation
        # dynamically between 0.3 km and 2.5 km in visual Z space so differences are clearly legible.
        min_up = min(up_m_list) if up_m_list else 0.0
        max_up = max(up_m_list) if up_m_list else 0.0
        
        if max_up - min_up < 1e-6:
            z_scaled = [1.0 for _ in up_m_list]
        else:
            z_scaled = [0.3 + ((v - min_up) / (max_up - min_up)) * 2.2 for v in up_m_list]
        
        lines_x = []
        lines_y = []
        lines_z = []
        lines_hover = []
        for st, lon, lat, z_val, up_val, dt in zip(stations, lons, lats, z_scaled, up_m_list, dates_used):
            txt = f"Station: {st}<br>Real Uplift: {up_val * 1000:.1f} mm ({up_val:.4f} m)<br>Date: {dt}"
            lines_x.extend([lon, lon, None])
            lines_y.extend([lat, lat, None])
            lines_z.extend([0.05, z_val, None])
            lines_hover.extend([txt, txt, None])
        
        # Geodetic spatial interpolation (IDW with exponent 2.5 simulating elastic Mogi deformation decay)
        min_lat, max_lat = min(lats) - 0.015, max(lats) + 0.015
        min_lon, max_lon = min(lons) - 0.015, max(lons) + 0.015
        
        # 1. Vertex grid for 3D Surface mesh (30x30 vertices - optimized for smooth rendering & low RAM footprint)
        grid_dim = 30
        grid_lats_mat, grid_lons_mat = np.meshgrid(
            np.linspace(min_lat, max_lat, grid_dim),
            np.linspace(min_lon, max_lon, grid_dim)
        )
        gc_pts = np.column_stack((grid_lats_mat.ravel(), grid_lons_mat.ravel()))
        st_c = np.column_stack((lats, lons))
        dists = np.linalg.norm(gc_pts[:, None, :] - st_c[None, :, :], axis=2)
        weights = 1.0 / np.maximum(dists**2.5, 1e-10)
        st_v_np = np.array(up_m_list)
        grid_up_vals = np.sum(weights * st_v_np, axis=1) / np.sum(weights, axis=1)
        
        if max_up - min_up < 1e-6:
            grid_z_scaled = [1.0 for _ in grid_up_vals]
        else:
            grid_z_scaled = [0.3 + ((v - min_up) / (max_up - min_up)) * 2.2 for v in grid_up_vals]
            
        # 2. Continuous 2D geographic polygon surface (GeoJSON cells for choroplethmapbox / densitymapbox)
        grid_lats_1d = np.linspace(min_lat, max_lat, grid_dim)
        grid_lons_1d = np.linspace(min_lon, max_lon, grid_dim)
        N = len(grid_lats_1d) - 1
        M = len(grid_lons_1d) - 1
        clats = (grid_lats_1d[:-1] + grid_lats_1d[1:]) / 2.0
        clons = (grid_lons_1d[:-1] + grid_lons_1d[1:]) / 2.0
        c_lats_mat, c_lons_mat = np.meshgrid(clats, clons, indexing='ij')
        gc_cells = np.column_stack((c_lats_mat.ravel(), c_lons_mat.ravel()))
        dists_cells = np.linalg.norm(gc_cells[:, None, :] - st_c[None, :, :], axis=2)
        weights_cells = 1.0 / np.maximum(dists_cells**2.5, 1e-10)
        cell_up_vals = np.round(np.sum(weights_cells * st_v_np, axis=1) / np.sum(weights_cells, axis=1), 5).tolist()
        
        features = [
            {
                'type': 'Feature',
                'id': f'c_{i*M+j}',
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[[round(float(grid_lons_1d[j]), 5), round(float(grid_lats_1d[i]), 5)],
                                     [round(float(grid_lons_1d[j+1]), 5), round(float(grid_lats_1d[i]), 5)],
                                     [round(float(grid_lons_1d[j+1]), 5), round(float(grid_lats_1d[i+1]), 5)],
                                     [round(float(grid_lons_1d[j]), 5), round(float(grid_lats_1d[i+1]), 5)],
                                     [round(float(grid_lons_1d[j]), 5), round(float(grid_lats_1d[i]), 5)]]]
                }
            }
            for i in range(N) for j in range(M)
        ]
        locs = [f'c_{k}' for k in range(N * M)]
        hover_texts = [
            f"<b>Interpolated Uplift Surface</b><br>Value: {val * 1000:.1f} mm ({val:.4f} m)<br>Lat: {gc_cells[k,0]:.4f}, Lon: {gc_cells[k,1]:.4f}"
            for k, val in enumerate(cell_up_vals)
        ]
        
        interp_grid = {
            'lats': np.round(gc_pts[:, 0], 5).tolist(),
            'lons': np.round(gc_pts[:, 1], 5).tolist(),
            'up_m': np.round(grid_up_vals, 5).tolist(),
            'z_scaled': np.round(grid_z_scaled, 3).tolist(),
            'grid_lats_2d': np.round(grid_lats_mat, 5).tolist(),
            'grid_lons_2d': np.round(grid_lons_mat, 5).tolist(),
            'grid_up_2d': np.round(grid_up_vals.reshape(grid_dim, grid_dim), 5).tolist(),
            'grid_z_2d': np.round(np.array(grid_z_scaled).reshape(grid_dim, grid_dim), 3).tolist(),
            'geojson': {
                'type': 'FeatureCollection',
                'features': features
            },
            'cell_locs': locs,
            'cell_up_m': cell_up_vals,
            'cell_hover': hover_texts
        }
        
        del gc_pts, st_c, dists, weights, st_v_np, grid_up_vals, c_lats_mat, c_lons_mat, gc_cells, dists_cells, weights_cells
        logger.info(f"Elaborate {len(stations)} stazioni GNSS e generata superficie geografica continua da {path.name}")
        
        return {
            'status': 'success',
            'type': 'uplift',
            'filename': path.name,
            'count': len(stations),
            'stations': stations,
            'lons': lons,
            'lats': lats,
            'up_m': up_m_list,
            'z_scaled': z_scaled,
            'dates': dates_used,
            'lines': {
                'x': lines_x,
                'y': lines_y,
                'z': lines_z,
                'hover': lines_hover
            },
            'surface': {
                'x': lons,
                'y': lats,
                'z': z_scaled
            },
            'interp_grid': interp_grid
        }
    except Exception as e:
        logger.error(f"Error during uplift processing: {e}", exc_info=True)
        return {'error': f"Uplift processing error: {str(e)}"}


def _load_station_coordinates(search_dir: Path, stations_path: str | Path | None = None) -> dict[str, tuple[float, float]]:
    """Locate and load flegrei_station_coordinates.csv into {station: (lat, lon)}."""
    candidates = []
    if stations_path:
        p = Path(stations_path)
        if p.exists():
            candidates.append(p)
    candidates.extend([
        search_dir / 'flegrei_station_coordinates.csv',
        BASE_DIR / 'Dati_tomografia' / 'flegrei_station_coordinates.csv',
        BASE_DIR / 'flegrei_station_coordinates.csv'
    ])
    
    coord_file = next((f for f in candidates if f.exists()), None)
    if not coord_file:
        logger.warning("flegrei_station_coordinates.csv non trovato nei percorsi standard.")
        return {}
        
    try:
        df = _read_csv_flexible(coord_file)
        df.columns = [c.strip().lower() for c in df.columns]
        
        st_col = next((c for c in df.columns if 'station' in c or 'staz' in c), None)
        lat_col = next((c for c in df.columns if 'lat' in c), None)
        lon_col = next((c for c in df.columns if 'lon' in c), None)
        
        if not all([st_col, lat_col, lon_col]):
            return {}
            
        return {
            str(st).strip().upper(): (float(lat), float(lon))
            for st, lat, lon in zip(df[st_col], df[lat_col], df[lon_col])
        }
    except Exception as e:
        logger.error(f"Errore lettura file coordinate stazioni: {e}")
        return {}


def process_stations_data(stations_path: str | Path) -> dict[str, Any]:
    """Load station coordinates and format them for visualization."""
    try:
        p = Path(stations_path)
        coord_map = _load_station_coordinates(p.parent if p.exists() else BASE_DIR, stations_path=stations_path)
        if not coord_map:
            return {'error': 'No station coordinates found in file.'}
        
        names = []
        lats = []
        lons = []
        hover_texts = []
        for name, (lat, lon) in coord_map.items():
            names.append(name)
            lats.append(lat)
            lons.append(lon)
            hover_texts.append(f"<b>Station: {name}</b><br>Lat: {lat:.5f}°<br>Lon: {lon:.5f}°")
            
        return {
            'names': names,
            'lats': lats,
            'lons': lons,
            'z': [0.05 for _ in names],
            'hover': hover_texts,
            'count': len(names)
        }
    except Exception as e:
        logger.error(f"Error processing station data: {e}", exc_info=True)
        return {'error': f"Error processing stations: {str(e)}"}
