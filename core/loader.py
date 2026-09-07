import logging
import pandas as pd
import numpy as np
from typing import Any
from datetime import datetime
from core.config import (
    MIN_MAGNITUDE, MISSING_MAG_VALUE, MISSING_DEPTH_VALUE, CSV_SCHEMA
)


logger = logging.getLogger(__name__)

def _make_hover(df: pd.DataFrame) -> list[str]:
    """Generate descriptive hover text strings using vectorized operations."""
    # Vectorized check for missing flags (if we added them during load)
    mag_labels = df['mag'].astype(str)
    if 'mag_is_missing' in df.columns:
        mag_labels = np.where(df['mag_is_missing'], "N.D. (missing)", df['mag'].astype(str))
    
    dep_labels = df['depth'].abs().map('{:.4f}'.format) + " km"
    if 'depth_is_missing' in df.columns:
        dep_labels = np.where(df['depth_is_missing'], "N.D. (missing)", dep_labels)

    return (
        "Date: " + df['time_dt'].dt.strftime('%d-%m-%Y %H:%M') + "<br>" +
        "Magnitude: " + mag_labels + "<br>" +
        "Latitude: " + df['lat'].map('{:.4f}'.format) + "<br>" +
        "Longitude: " + df['lon'].map('{:.4f}'.format) + "<br>" +
        "Depth: " + dep_labels
    ).tolist()

def precompute_visual_data(df: pd.DataFrame) -> dict[str, Any]:
    """Pre-calculate expensive data structures for visualizations."""
    logger.info("Packaging visualization data...")
    
    # 1. Hover Strings
    all_hover = _make_hover(df)
    
    # 2. Date grouping for animation (Vectorized)
    df['date_str'] = df['time_dt'].dt.strftime('%Y-%m-%d')
    counts = df.groupby('date_str').size().sort_index()
    
    unique_dates = counts.index.tolist()
    date_counts = counts.tolist()
    date_to_cum = counts.cumsum().to_dict()
        
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
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        raise ValueError(f"Failed to read CSV: {e}")

    # Drop rows ONLY if they are missing essential coordinates or time
    essential_cols = ['lat', 'lon', 'time']
    df = df.dropna(subset=[c for c in essential_cols if c in df.columns])
    
    # Ensure chronological order - CRITICAL for animation slicing
    if df['time'].astype(str).str.match(r'^\d+(\.\d+)?$').all():
        df['time_dt'] = pd.to_datetime(pd.to_numeric(df['time']), origin='1899-12-30', unit='D')
    else:
        df['time_dt'] = pd.to_datetime(df['time'], errors='coerce')
    if hasattr(df['time_dt'].dt, 'tz') and df['time_dt'].dt.tz is not None:
        df['time_dt'] = df['time_dt'].dt.tz_localize(None)
    df = df.dropna(subset=['time_dt'])
    df = df.reset_index(drop=True)

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
        raise ValueError(f"No seismic events found with M ≥ {MIN_MAGNITUDE}.")

    # Fast datetime parsing (removed redundant second parsing)
    
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


    # Pre-calculate dates_num (days since first event)
    min_t = df['time_dt'].min()
    df['dates_num'] = (df['time_dt'] - min_t).dt.total_seconds() / 86400.0
    
    # Precompute fast Float32 arrays for binary buffer
    lon_f32 = df['lon'].to_numpy(dtype=np.float32)
    lat_f32 = df['lat'].to_numpy(dtype=np.float32)
    dep_f32 = (-df['depth']).to_numpy(dtype=np.float32)
    mag_f32 = df['mag'].to_numpy(dtype=np.float32)
    dnum_f32 = df['dates_num'].to_numpy(dtype=np.float32)

    count = len(df)
    binary_buffer = b"".join([
        np.array([count, 0], dtype=np.float32).tobytes(),
        lon_f32.tobytes(),
        lat_f32.tobytes(),
        mag_f32.tobytes(),
        dep_f32.tobytes(),
        dnum_f32.tobytes(),
    ])

    # Pre-calculate visual pack
    visual_pack = precompute_visual_data(df)

    # Extract as lists for JSON serialization (Webview)
    latitude = lat_f32.tolist()
    longitude = lon_f32.tolist()
    depth = dep_f32.tolist() # Store as negative for depth
    magnitude = mag_f32.tolist()
    times = df['time_dt'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist()
    dates_num = dnum_f32.tolist()

    date_range = f"{df['time_dt'].iloc[0].strftime('%d-%m-%Y')} → {df['time_dt'].iloc[-1].strftime('%d-%m-%Y')}"
    bbox = (float(df['lat'].min()), float(df['lon'].min()), float(df['lat'].max()), float(df['lon'].max()))
    logger.info(f"Loaded {len(df)} seismic events (M >= {MIN_MAGNITUDE}).")

    return {
        'latitude': latitude,
        'longitude': longitude,
        'depth': depth,
        'magnitude': magnitude,
        'times': times,
        'dates_num': dates_num,
        'bbox': bbox,
        'visual_pack': visual_pack,
        'origin_lat': float(df['lat'].mean()),
        'origin_lon': float(df['lon'].mean()),
        'binary_buffer': binary_buffer,
        'summary': {
            'event_count': len(df),
            'date_range': date_range,
            'total_days': visual_pack['total_days'],
        },
    }



