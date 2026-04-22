import pandas as pd
import logging
from typing import Any

logger = logging.getLogger(__name__)

MIN_MAGNITUDE: float = 0.5

def _make_hover(df: pd.DataFrame) -> list[str]:
    """Generate descriptive hover text strings from a DataFrame using vectorized operations."""
    return (
        "Date: " + pd.to_datetime(df['time']).dt.strftime('%d-%m-%Y %H:%M') + "<br>" +
        "Magnitude: " + df['mag'].astype(str) + "<br>" +
        "Latitude: " + df['lat'].map('{:.4f}'.format) + "<br>" +
        "Longitude: " + df['lon'].map('{:.4f}'.format) + "<br>" +
        "Depth: " + df['depth'].abs().map('{:.4f}'.format) + " km"
    ).tolist()

def precompute_visual_data(df: pd.DataFrame) -> dict[str, Any]:
    """Pre-calculate expensive data structures for visualizations."""
    logger.info("Packaging visualization data...")
    
    # 1. Hover Strings
    all_hover = _make_hover(df)
    
    # 2. Date grouping for animation
    df['date_str'] = df['time_dt'].dt.strftime('%Y-%m-%d')
    unique_dates = sorted(df['date_str'].unique())
    # Count events per unique date
    counts_map = df.groupby('date_str').size().to_dict()
    date_counts = [int(counts_map.get(d, 0)) for d in unique_dates]
    
    cum = 0
    date_to_cum = {}
    for d in unique_dates:
        cum += int(counts_map.get(d, 0))
        date_to_cum[d] = cum
        
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
    """Parse a seismic CSV and return extracted data arrays.

    Returns a dict with keys: latitude, longitude, depth, magnitude, times,
    dates_num, and a summary dict with event_count, date_range.
    Raises ValueError if the CSV is invalid or has no qualifying events.
    """
    try:
        # 1. Read header to detect columns by name
        df_full = pd.read_csv(source_file, header=0)
        cols = df_full.columns.tolist()

        # Mapping dictionary for common earthquake CSV headers
        mapping = {
            'time': ['time', 'Date', 'DateTime', 'UTC', 'time_utc'],
            'lat': ['lat', 'latitude', 'Latitude', 'LAT'],
            'lon': ['lon', 'longitude', 'Longitude', 'LON'],
            'depth': ['depth', 'Depth', 'depth_km', 'DEPTH'],
            'mag': ['mag', 'magnitude', 'Magnitude', 'Mag', 'MAG']
        }

        found_mapping = {}
        for internal_name, aliases in mapping.items():
            for alias in aliases:
                if alias in cols:
                    found_mapping[internal_name] = alias
                    break
        
        # If we found all 5 columns by name, use them
        if len(found_mapping) == 5:
            df = df_full[[found_mapping[k] for k in ['time', 'lat', 'lon', 'depth', 'mag']]]
            df.columns = ['time', 'lat', 'lon', 'depth', 'mag']
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

    # Drop malformed rows and filter by magnitude
    df = df.dropna()
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



