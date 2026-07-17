import requests
import logging
import csv
from datetime import datetime
from typing import Any
from core.config import (
    GOSSIP_BASE_URL, 
    TEMP_DIR, 
    DEFAULT_LOCATED_ONLY, 
    DEFAULT_EXCLUDE_MISSING,

    CSV_CANONICAL_HEADER
)
from core.utils import parse_seismic_date

logger = logging.getLogger(__name__)

def _fmt_num(val: float | int | str | None, precision: int) -> str:
    """Helper to safely format numeric values or return an empty string."""
    try:
        return f"{float(val):.{precision}f}"
    except (ValueError, TypeError):
        return ""

def _extract_md_obj(magnitudos: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract preferred duration magnitude (MD) dictionary or fallback to first available."""
    if not magnitudos:
        return {}
    return next((m for m in magnitudos if m.get('type') == 'D'), magnitudos[0])

def fetch_ingv_data(params: dict[str, Any]) -> str:
    """
    Fetch seismic data from INGV (GOSSIP) and save it to a temporary CSV.
    Returns the path to the generated CSV file.
    """
    network = params.get('network')
    if not network:
        raise ValueError("Geographic area is required.")

    # Using the new robust date parser for start/end
    start_dt = parse_seismic_date(f"{params['startdate']} {params['starttime']}")
    end_dt = parse_seismic_date(f"{params['enddate']} {params['endtime']}")
    
    if not start_dt or not end_dt:
        raise ValueError("Invalid start or end date format.")

    min_mag = float(params.get('minmag', 0.0))
    max_mag = float(params.get('maxmag', 10.0))
    level = int(params.get('level', 0))
    only_located = params.get('located', DEFAULT_LOCATED_ONLY)
    exclude_missing = params.get('excludeMissing', DEFAULT_EXCLUDE_MISSING)

    # Base URL from config
    base_url = f"{GOSSIP_BASE_URL}/{network}"
    
    years = range(start_dt.year, end_dt.year + 1)
    all_events = []

    for year in years:
        url = f"{base_url}/{year}/events.json"
        logger.info(f"Fetching data from: {url}")
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                year_events = response.json()
                all_events.extend(year_events)
            else:
                logger.warning(f"Failed to fetch data for year {year}: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching data for year {year}: {e}")

    # Filter events
    filtered_events = []
    
    logger.info(f"Starting filtering for {len(all_events)} events. Range: {start_dt} to {end_dt}, Mag: {min_mag}-{max_mag}, Level: {level}, OnlyLocated: {only_located}")

    reject_reasons = {"date": 0, "mag": 0, "level": 0, "loc": 0, "parse": 0}

    for e in all_events:
        # Date/Time filter
        e_dt = parse_seismic_date(e.get('date'))
        if not e_dt:
            reject_reasons["parse"] += 1
            continue

        if not (start_dt <= e_dt <= end_dt):
            reject_reasons["date"] += 1
            continue

        # 2. Magnitude filter
        md_obj = _extract_md_obj(e.get('magnitudos', []))
        mag = md_obj.get('value')
            
        if mag is None:
            if exclude_missing or min_mag > 0.1:
                reject_reasons["mag"] += 1
                continue
        elif not (min_mag <= mag <= max_mag):
            reject_reasons["mag"] += 1
            continue

        # 3. Level filter
        if level > 0:
            e_level = e.get('level')
            if not isinstance(e_level, str):
                reject_reasons["level"] += 1
                continue
                
            e_level_lower = e_level.lower()
            if level == 2: # Bollettino
                if e_level_lower == "automatico" or e_level_lower == "rivisto":
                    reject_reasons["level"] += 1
                    continue
            elif level == 1: # Riviste
                if e_level_lower == "automatico":
                    reject_reasons["level"] += 1
                    continue

        # 4. Location & Missing Data check
        loc = e.get('location', {})
        if only_located:
            if not loc or loc.get('latitude') is None or loc.get('longitude') is None:
                reject_reasons["loc"] += 1
                continue
        
        if exclude_missing:
            # We already checked mag above. Now check depth.
            if not loc or loc.get('depth') is None:
                reject_reasons["loc"] += 1
                continue

        filtered_events.append(e)

    logger.info(f"Filtering complete. Passed: {len(filtered_events)}. Rejections: {reject_reasons}")

    if not filtered_events:
        raise ValueError("No events found with the selected filters.")

    # Sort events by date
    filtered_events.sort(key=lambda x: x['date'])

    # Generate CSV (following the INGV format)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    filename = f"ingv_{network}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = TEMP_DIR / filename

    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(CSV_CANONICAL_HEADER)
        
        for e in filtered_events:
            loc = e.get('location', {})
            md = _extract_md_obj(e.get('magnitudos', []))
            
            row = [
                e.get('id', ''),
                e.get('date', ''), 
                _fmt_num(loc.get('latitude'), 6),
                _fmt_num(loc.get('longitude'), 6),
                _fmt_num(loc.get('depth'), 2),
                _fmt_num(md.get('value'), 2),
                _fmt_num(md.get('error', 0.3), 2),
                e.get('area', ''),
                e.get('type', ''),
                e.get('level', '')
            ]
            writer.writerow(row)

    return str(filepath)
