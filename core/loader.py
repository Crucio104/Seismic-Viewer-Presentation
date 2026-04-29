import logging
from typing import Any

logger = logging.getLogger(__name__)

MIN_MAGNITUDE: float = -10.0

def _make_hover(df) -> list[str]:
    """Generate descriptive hover text strings using vectorized operations."""
    import pandas as pd
    import numpy as np

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

def precompute_visual_data(df) -> dict[str, Any]:
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

    }

def load_csv(source_file: str) -> dict[str, Any]:
    """Parse a seismic CSV and return extracted data arrays."""
    import pandas as pd
    try:
        # 1. Read ONLY the header first to detect columns
        header_df = pd.read_csv(source_file, header=0, nrows=0)
        cols = header_df.columns.tolist()

        # Mapping dictionary for common earthquake CSV headers
        mapping = {
            'time': ['time', 'date', 'datetime', 'utc', 'time_utc', 'origintime'],
            'lat': ['lat', 'latitude'],
            'lon': ['lon', 'longitude'],
            'depth': ['depth', 'depth_km'],
            'mag': ['mag', 'magnitude', 'md', 'ml', 'mw']
        }

        # Robust case-insensitive and stripped matching
        cols_clean = {c.strip().lower(): c for c in cols if isinstance(c, str)}

        found_mapping = {}
        for internal_name, aliases in mapping.items():
            for alias in aliases:
                if alias.lower() in cols_clean:
                    found_mapping[internal_name] = cols_clean[alias.lower()]
                    break
        
        # If we found all 5 columns by name, use them for optimized read
        if len(found_mapping) == 5:
            # Re-read ONLY the necessary columns to save memory
            df = pd.read_csv(source_file, usecols=list(found_mapping.values()))
            # Rename for internal consistency
            rename_map = {v: k for k, v in found_mapping.items()}
            df = df.rename(columns=rename_map)
        else:
            # Fallback to positional indices if names don't match
            # Expecting: [1]Time, [2]Lat, [3]Lon, [4]Depth, [5]Mag
            logger.warning("Column names not recognized, falling back to positional indices.")
            df = pd.read_csv(
                source_file, 
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
    
    # Flag missing depth/magnitude BEFORE filling them
    if 'depth' in df.columns:
        df['depth_is_missing'] = df['depth'].isna()
        df['depth'] = df['depth'].fillna(0.0)
    if 'mag' in df.columns:
        df['mag_is_missing'] = df['mag'].isna()
        df['mag'] = df['mag'].fillna(0.1)

    # Filter by magnitude (now using the permissive -10.0 default)
    df = df[df['mag'] >= MIN_MAGNITUDE]

    if df.empty:
        raise ValueError(f"No seismic events found with M ≥ {MIN_MAGNITUDE}.")

    # Fast datetime parsing
    df['time_dt'] = pd.to_datetime(df['time'], errors='coerce')
    df = df.dropna(subset=['time_dt'])
    
    # Sort for visualization consistency
    df = df.sort_values('time_dt').reset_index(drop=True)


    # Pre-calculate dates_num (days since first event)
    min_t = df['time_dt'].min()
    df['dates_num'] = (df['time_dt'] - min_t).dt.total_seconds() / 86400.0
    
    # Pre-calculate visual pack
    visual_pack = precompute_visual_data(df)

    # Extract as lists for JSON serialization (Webview)
    latitude = df['lat'].tolist()
    longitude = df['lon'].tolist()
    depth = (-df['depth']).tolist() # Store as negative for depth
    magnitude = df['mag'].tolist()
    times = df['time'].tolist()
    dates_num = df['dates_num'].tolist()

    date_range = f"{df['time_dt'].iloc[0].strftime('%d-%m-%Y')} → {df['time_dt'].iloc[-1].strftime('%d-%m-%Y')}"
    bbox = (df['lat'].min(), df['lon'].min(), df['lat'].max(), df['lon'].max())
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
        'summary': {
            'event_count': len(df),
            'date_range': date_range,
        },
    }



