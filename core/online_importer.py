import requests
import logging
import csv
import json
import time
from datetime import datetime
from typing import Any, Callable
from core.config import (
    GOSSIP_BASE_URL, 
    TEMP_DIR, 
    INGV_CACHE_DIR,
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

def _fetch_year(year: int, network: str, on_progress: Callable[[str], None] | None = None) -> list[dict[str, Any]]:
    """
    Fetch annual events.json from INGV with streaming, local disk caching and conditional ETag.
    """
    INGV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = INGV_CACHE_DIR / f"{network}_{year}.json"
    meta_file = INGV_CACHE_DIR / f"{network}_{year}.meta.json"

    current_year = datetime.now().year
    is_past_year = year < current_year

    # Past years are immutable: load directly from local cache if present
    if is_past_year and cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                logger.info(f"Loaded year {year} ({network}) from local cache: {cache_file}")
                if on_progress:
                    on_progress(f"Caricamento anno {year} dalla cache locale...")
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read local cache {cache_file}: {e}")

    url = f"{GOSSIP_BASE_URL}/{network}/{year}/events.json"
    logger.info(f"Fetching data from: {url}")
    if on_progress:
        on_progress(f"Connessione a INGV per l'anno {year}...")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*'
    }

    # Conditional HTTP request using ETag for current year
    if cache_file.exists() and meta_file.exists():
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                etag = meta.get('etag')
                if etag:
                    headers['If-None-Match'] = etag
        except Exception:
            pass

    try:
        with requests.Session() as s:
            # 20s connection timeout, 60s per-chunk read timeout (resets with each received chunk)
            resp = s.get(url, headers=headers, stream=True, timeout=(20, 60))

            if resp.status_code == 304 and cache_file.exists():
                logger.info(f"INGV data for year {year} is unchanged (304 Not Modified). Using local cache.")
                if on_progress:
                    on_progress(f"Dati INGV {year} aggiornati, uso cache...")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)

            if resp.status_code == 200:
                total_bytes = int(resp.headers.get('Content-Length', 0))
                content = bytearray()
                last_report = time.time()

                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        content.extend(chunk)
                        now = time.time()
                        if on_progress and (now - last_report > 1.2):
                            last_report = now
                            dl_mb = len(content) / (1024 * 1024)
                            if total_bytes > 0:
                                tot_mb = total_bytes / (1024 * 1024)
                                on_progress(f"Download INGV {year}: {dl_mb:.1f}MB / {tot_mb:.1f}MB...")
                            else:
                                on_progress(f"Download INGV {year}: {dl_mb:.1f}MB...")

                data = json.loads(content)

                # Persist to local cache
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f)
                    new_etag = resp.headers.get('ETag')
                    if new_etag:
                        with open(meta_file, 'w', encoding='utf-8') as f:
                            json.dump({'etag': new_etag, 'updated_at': datetime.now().isoformat()}, f)
                except Exception as ce:
                    logger.warning(f"Failed to write INGV cache: {ce}")

                return data
            elif resp.status_code == 404:
                logger.warning(f"No INGV data found for year {year} (HTTP 404).")
                return []
            else:
                logger.warning(f"Failed to fetch data for year {year}: HTTP {resp.status_code}")
                raise RuntimeError(f"Il server INGV ha restituito errore HTTP {resp.status_code} per l'anno {year}.")
    except requests.exceptions.Timeout as te:
        if cache_file.exists():
            logger.warning(f"Timeout on year {year}, falling back to local cache: {te}")
            if on_progress:
                on_progress(f"Server INGV lento: uso cache locale per {year}...")
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        logger.error(f"Timeout fetching data for year {year}: {te}")
        raise TimeoutError(
            f"Il server INGV (terremoti.ov.ingv.it) ha impiegato troppo tempo a rispondere per l'anno {year}. "
            "Il server dell'Osservatorio è momentaneamente lento o sovraccarico; riprova tra poco."
        ) from te
    except Exception as e:
        if cache_file.exists():
            logger.warning(f"Error on year {year}, falling back to local cache: {e}")
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        logger.error(f"Error fetching data for year {year}: {e}")
        raise

def fetch_ingv_data(params: dict[str, Any], on_progress: Callable[[str], None] | None = None) -> str:
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

    years = list(range(start_dt.year, end_dt.year + 1))
    all_events = []

    for y in years:
        year_events = _fetch_year(y, network, on_progress)
        all_events.extend(year_events)

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
            if level == 2 and e_level_lower in ("automatico", "rivisto"):
                reject_reasons["level"] += 1
                continue
            elif level == 1 and e_level_lower == "automatico":
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
