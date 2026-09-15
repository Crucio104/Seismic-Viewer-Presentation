import logging
import pandas as pd
import numpy as np
from typing import Any
from datetime import datetime
from core.config import (
    MIN_MAGNITUDE, MISSING_MAG_VALUE, MISSING_DEPTH_VALUE, CSV_SCHEMA, SECONDS_PER_DAY
)
from core.swarm_detector import detect_ingv_swarms


logger = logging.getLogger(__name__)

def _make_hover(df: pd.DataFrame) -> list[str]:
    """Generate descriptive hover text strings avoiding intermediate Pandas Series overhead."""
    dates = df['time_dt'].dt.strftime('%d-%m-%Y %H:%M').to_numpy()
    lats = df['lat'].to_numpy(dtype=float)
    lons = df['lon'].to_numpy(dtype=float)
    deps = np.abs(df['depth'].to_numpy(dtype=float))
    mags = df['mag'].astype(str).to_numpy()

    has_mag_missing = 'mag_is_missing' in df.columns
    has_dep_missing = 'depth_is_missing' in df.columns
    mag_miss = df['mag_is_missing'].to_numpy() if has_mag_missing else None
    dep_miss = df['depth_is_missing'].to_numpy() if has_dep_missing else None

    result: list[str] = []
    n = len(df)
    for i in range(n):
        m_label = "N.D. (missing)" if (has_mag_missing and mag_miss[i]) else mags[i]
        d_label = "N.D. (missing)" if (has_dep_missing and dep_miss[i]) else f"{deps[i]:.4f} km"
        result.append(
            f"Date: {dates[i]}<br>"
            f"Magnitude: {m_label}<br>"
            f"Latitude: {lats[i]:.4f}<br>"
            f"Longitude: {lons[i]:.4f}<br>"
            f"Depth: {d_label}"
        )
    return result

def precompute_visual_data(df: pd.DataFrame) -> dict[str, Any]:
    """Pre-calculate expensive data structures for visualizations with minimal memory footprint."""
    logger.info("Packaging visualization data...")
    
    # 1. Hover Strings
    all_hover = _make_hover(df)
    
    # 2. Date grouping for animation (without allocating a 50k temporary string column on df)
    date_counts_series = df['time_dt'].dt.floor('D').value_counts().sort_index()
    unique_dates = [ts.strftime('%Y-%m-%d') for ts in date_counts_series.index]
    date_counts = date_counts_series.tolist()
    date_to_cum = dict(zip(unique_dates, date_counts_series.cumsum().tolist()))
        
    return {
        'hover': all_hover,
        'unique_dates': unique_dates,
        'date_to_cum': date_to_cum,
        'mag_range': [float(df['mag'].min()), float(df['mag'].max())],
        'dep_range': [float((-df['depth']).min()), float((-df['depth']).max())],
        'date_range': [float(df['dates_num'].min()), float(df['dates_num'].max())],
        'date_counts': date_counts,
        'total_days': int((df['time_dt'].max() - df['time_dt'].min()).days) + 1,
    }

def load_csv(source_file: str) -> dict[str, Any]:
    """Parse a seismic CSV and return extracted data arrays."""
    try:
        with open(source_file, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline()
            sep = ';' if ';' in first_line else ','

        # 1. Read ONLY the header first to detect columns
        header_df = pd.read_csv(source_file, sep=sep, header=0, nrows=0)
        cols = header_df.columns.tolist()

        # Robust case-insensitive and stripped matching
        cols_clean = {c.strip().lower(): c for c in cols if isinstance(c, str)}

        found_mapping = {}
        for internal_name, aliases in CSV_SCHEMA.items():
            for alias in aliases:
                if alias.lower() in cols_clean:
                    found_mapping[internal_name] = cols_clean[alias.lower()]
                    break
        
        # If we found all 5 columns by name, use them for optimized read
        if len(found_mapping) == 5:
            # Re-read ONLY the necessary columns to save memory
            df = pd.read_csv(source_file, sep=sep, usecols=list(found_mapping.values()))
            # Rename for internal consistency
            rename_map = {v: k for k, v in found_mapping.items()}
            df = df.rename(columns=rename_map)
        else:
            # Fallback to positional indices if names don't match
            # Expecting: [1]Time, [2]Lat, [3]Lon, [4]Depth, [5]Mag
            logger.warning("Column names not recognized, falling back to positional indices.")
            df = pd.read_csv(
                source_file, 
                sep=sep,
                usecols=[1, 2, 3, 4, 5],
                names=['time', 'lat', 'lon', 'depth', 'mag'],
                header=0
            )
        essential_cols = ['lat', 'lon', 'time']
        df = df.dropna(subset=[c for c in essential_cols if c in df.columns])
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        raise ValueError(f"Failed to read CSV: {e}")

    return process_seismic_dataframe(df)


def process_seismic_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    """Process a seismic DataFrame and return extracted data arrays for visualization."""
    if df.empty:
        raise ValueError(f"No seismic events found with M >= {MIN_MAGNITUDE}.")

    # Ensure chronological order - CRITICAL for animation slicing
    if 'time_dt' not in df.columns and 'time' in df.columns:
        if df['time'].astype(str).str.match(r'^\d+(\.\d+)?$').all():
            df['time_dt'] = pd.to_datetime(pd.to_numeric(df['time']), origin='1899-12-30', unit='D')
        else:
            try:
                df['time_dt'] = pd.to_datetime(df['time'], format='ISO8601')
            except Exception:
                df['time_dt'] = pd.to_datetime(df['time'], errors='coerce', format='mixed')
    
    if 'time_dt' in df.columns:
        if hasattr(df['time_dt'].dt, 'tz') and df['time_dt'].dt.tz is not None:
            df['time_dt'] = df['time_dt'].dt.tz_localize(None)
        df = df.dropna(subset=['time_dt'])
        df = df.reset_index(drop=True)
        if 'time' in df.columns:
            del df['time'] # Immediately free raw CSV strings

    # Flag missing depth/magnitude BEFORE filling them
    if 'depth' in df.columns:
        df['depth_is_missing'] = df['depth'].isna()
        df['depth'] = df['depth'].fillna(MISSING_DEPTH_VALUE)
    if 'mag' in df.columns:
        df['mag_is_missing'] = df['mag'].isna()
        df['mag'] = df['mag'].fillna(MISSING_MAG_VALUE)

    # Filter by magnitude (now using the permissive -10.0 default)
    df = df[df['mag'] >= MIN_MAGNITUDE]

    if df.empty:
        raise ValueError(f"No seismic events found with M >= {MIN_MAGNITUDE}.")

    # --- SANITY CHECKS ---
    initial_count = len(df)
    
    # 1. Geographic Bounds Check
    df = df[(df['lat'].between(-90, 90)) & (df['lon'].between(-180, 180))]
    
    # 2. Temporal Bounds Check (No future dates beyond timezone discrepancy)
    df = df[df['time_dt'] <= datetime.now() + pd.Timedelta(days=1)]
    
    # 3. Depth check (Reasonable range: -10km to 800km)
    df = df[df['depth'].between(-10, 800)]
    
    removed = initial_count - len(df)
    if removed > 0:
        logger.warning(f"Sanity check: removed {removed} invalid records (out of bounds, future dates, or impossible depth).")

    # Sort for visualization consistency
    df = df.sort_values('time_dt').reset_index(drop=True)

    # Pre-calculate dates_num (days since first event) directly in Float32 to save RAM
    dnum_f32 = ((df['time_dt'] - df['time_dt'].iloc[0]).dt.total_seconds() / SECONDS_PER_DAY).to_numpy(dtype=np.float32)
    df['dates_num'] = dnum_f32
    
    # Precompute fast Float32 arrays for binary buffer and core processing
    lon_f32 = df['lon'].to_numpy(dtype=np.float32)
    lat_f32 = df['lat'].to_numpy(dtype=np.float32)
    dep_f32 = (-df['depth']).to_numpy(dtype=np.float32)
    mag_f32 = df['mag'].to_numpy(dtype=np.float32)

    # Pre-calculate visual pack
    visual_pack = precompute_visual_data(df)

    # Detect INGV seismic swarms
    swarms = detect_ingv_swarms(df)

    # Keep dense NumPy float32 arrays to save RAM (avoiding ~8x Python float wrapper overhead)
    latitude = lat_f32
    longitude = lon_f32
    depth = dep_f32 # Store as negative for depth
    magnitude = mag_f32
    times = df['time_dt'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist()
    dates_num = dnum_f32

    date_range = f"{df['time_dt'].iloc[0].strftime('%d-%m-%Y')} → {df['time_dt'].iloc[-1].strftime('%d-%m-%Y')}"
    bbox = (float(df['lat'].min()), float(df['lon'].min()), float(df['lat'].max()), float(df['lon'].max()))
    logger.info(f"Loaded {len(df)} seismic events (M >= {MIN_MAGNITUDE}) and {len(swarms)} INGV swarms.")

    result = {
        'latitude': latitude,
        'longitude': longitude,
        'depth': depth,
        'depth_is_missing': df['depth_is_missing'].to_numpy() if 'depth_is_missing' in df.columns else np.zeros(len(df), dtype=bool),
        'magnitude': magnitude,
        'times': times,
        'dates_num': dates_num,
        'bbox': bbox,
        'visual_pack': visual_pack,
        'origin_lat': float(df['lat'].mean()),
        'origin_lon': float(df['lon'].mean()),
        'swarms': swarms,
        'swarms_count': len(swarms),
        'summary': {
            'event_count': len(df),
            'date_range': date_range,
            'total_days': visual_pack['total_days'],
            'swarms_count': len(swarms),
        },
    }
    result['binary_buffer'] = pack_seismic_binary(result)
    return result


def pack_seismic_binary(data: dict[str, Any]) -> bytes:
    """Pack seismic dictionary data into a compact binary Float32 buffer."""
    cluster = data.get('cluster', [])
    has_clusters = cluster is not None and len(cluster) > 0
    if 'binary_buffer' in data and not has_clusters:
        return data['binary_buffer']

    # Canonical key mapping
    lon_key = 'longitude' if 'longitude' in data else 'lon'
    lat_key = 'latitude' if 'latitude' in data else 'lat'
    mag_key = 'magnitude' if 'magnitude' in data else 'mag'
    dep_key = 'depth' if 'depth' in data else 'dep'
    dnum_key = 'dates_num' if 'dates_num' in data else 'dnum'

    count = len(data.get(lon_key, []))

    def _to_f32_bytes(key: str, length: int) -> bytes:
        arr = data.get(key)
        if arr is None or len(arr) == 0:
            return np.zeros(length, dtype=np.float32).tobytes()
        if isinstance(arr, np.ndarray) and arr.dtype == np.float32:
            return arr.tobytes()
        return np.array(arr, dtype=np.float32).tobytes()

    cluster_bytes = np.array(cluster, dtype=np.float32).tobytes() if has_clusters else b""

    buffer = b"".join([
        np.array([count, len(cluster)], dtype=np.float32).tobytes(),
        _to_f32_bytes(lon_key, count),
        _to_f32_bytes(lat_key, count),
        _to_f32_bytes(mag_key, count),
        _to_f32_bytes(dep_key, count),
        _to_f32_bytes(dnum_key, count),
        cluster_bytes
    ])
    if not has_clusters:
        data['binary_buffer'] = buffer
    return buffer
