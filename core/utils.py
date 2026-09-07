import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def parse_seismic_date(date_str: str) -> datetime | None:
    """
    Robustly parse date strings from various sources (INGV GOSSIP, CSV).
    Handles formats with/without microseconds and common separators.
    """
    if not date_str or not isinstance(date_str, str):
        return None
        
    # Standardize separators and strip trailing Z / offsets if present
    clean_str = date_str.replace('T', ' ').rstrip('Z').strip()
    # If offset like +00:00 or +01:00 exists, take first part
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
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
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
            
    logger.warning(f"Could not parse date string: {date_str}")
    return None
