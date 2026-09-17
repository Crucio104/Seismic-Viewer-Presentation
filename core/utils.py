import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import orjson  # type: ignore

    def parse_json_bytes_fast(content: bytes | bytearray) -> Any:
        """Parse JSON bytes using ultra-fast SIMD-accelerated orjson."""
        return orjson.loads(content)

    def read_json_fast(file_path: str | Path) -> Any:
        """Read and parse JSON from file using orjson."""
        with open(file_path, 'rb') as f:
            return orjson.loads(f.read())
except ImportError:
    try:
        import ujson  # type: ignore

        def parse_json_bytes_fast(content: bytes | bytearray) -> Any:
            return ujson.loads(content)

        def read_json_fast(file_path: str | Path) -> Any:
            with open(file_path, encoding='utf-8', errors='ignore') as f:
                return ujson.load(f)
    except ImportError:
        def parse_json_bytes_fast(content: bytes | bytearray) -> Any:
            return json.loads(content)

        def read_json_fast(file_path: str | Path) -> Any:
            with open(file_path, encoding='utf-8', errors='ignore') as f:
                return json.load(f)


def parse_seismic_date(date_val: Any) -> datetime | None:
    """
    Robustly parse date values from various sources (INGV GOSSIP, CSV, GeoJSON, Excel).
    Handles ISO formats, European formats (DD/MM/YYYY), numeric dates, and microsecond precision.
    """
    if date_val is None or (isinstance(date_val, float) and pd.isna(date_val)):
        return None

    if isinstance(date_val, datetime):
        return date_val

    # Handle numeric serial date (e.g., Excel serial day or Unix timestamp)
    if isinstance(date_val, (int, float)):
        try:
            if date_val > 1e9:  # Likely Unix timestamp in seconds
                return datetime.fromtimestamp(date_val)
            # Likely Excel serial date format (origin 1899-12-30)
            return pd.to_datetime(date_val, origin='1899-12-30', unit='D').to_pydatetime()
        except Exception:
            return None

    date_str = str(date_val).strip()
    if not date_str:
        return None

    # Standardize separators and strip trailing Z / offsets if present
    clean_str = date_str.replace('T', ' ').rstrip('Z').strip()
    if '+' in clean_str:
        clean_str = clean_str.split('+')[0].strip()

    # Fast-path for standard ISO / INGV formats (%Y-%m-%d %H:%M:%S[.f])
    if len(clean_str) >= 19 and clean_str[10] == ' ':
        fmt = "%Y-%m-%d %H:%M:%S.%f" if '.' in clean_str else "%Y-%m-%d %H:%M:%S"
        try:
            return datetime.strptime(clean_str, fmt)
        except ValueError:
            pass

    formats = [
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(clean_str, fmt)
        except ValueError:
            continue

    # Fallback to pandas robust parser for any exotic formatting
    try:
        ts = pd.to_datetime(date_str, errors='coerce')
        if pd.notna(ts):
            return ts.to_pydatetime()
    except Exception:
        pass

    logger.warning(f"Could not parse date: {date_val}")
    return None


def parse_seismic_date_series(series: pd.Series) -> pd.Series:
    """
    Vectorized parse of a pandas Series into timezone-naive datetime64[ns].
    Uses fast ISO8601 path first, Excel serial detection, with robust fallback.
    """
    if series.empty:
        return pd.Series(dtype='datetime64[ns]')

    # 1. Numeric serial dates
    if pd.api.types.is_numeric_dtype(series):
        try:
            return pd.to_datetime(series, origin='1899-12-30', unit='D')
        except Exception:
            pass
    else:
        # Sample first non-null element to check if it represents a string-encoded pure number
        non_nulls = series.dropna()
        if not non_nulls.empty:
            first_val = str(non_nulls.iloc[0]).strip()
            if first_val.replace('.', '', 1).isdigit():
                try:
                    num_series = pd.to_numeric(series, errors='coerce')
                    if num_series.notna().sum() > 0.8 * len(series):
                        return pd.to_datetime(num_series, origin='1899-12-30', unit='D')
                except Exception:
                    pass

    # 2. Fast ISO8601 path
    try:
        dt_series = pd.to_datetime(series, format='ISO8601')
        if dt_series.notna().sum() > 0.8 * len(series):
            return dt_series
    except Exception:
        pass

    # 3. Fast standard format trial
    try:
        dt_series = pd.to_datetime(series, format='%Y-%m-%d %H:%M:%S', errors='coerce')
        if dt_series.notna().sum() > 0.8 * len(series):
            return dt_series
    except Exception:
        pass

    # 4. Mixed format parsing
    try:
        dt_series = pd.to_datetime(series, errors='coerce', format='mixed')
        if dt_series.notna().sum() > 0.5 * len(series):
            return dt_series
    except Exception:
        pass

    # 5. Row-by-row fallback with parse_seismic_date
    parsed = series.map(parse_seismic_date)
    return pd.to_datetime(parsed, errors='coerce')

