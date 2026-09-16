import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import pickle
import numpy as np
import requests
import PIL.Image
import logging
import io
from functools import lru_cache
from typing import Any
from core.config import PALETTE_COLORS, MAP_CACHE_DIR

logger = logging.getLogger(__name__)

TILE_SIZE = 256
OSM_TILE_SERVER = "https://tile.openstreetmap.org"
USER_AGENT = "SeismicViewer/1.0 (academic-research; contact: seismic-viewer@local)"

def _deg2num(lat_deg: float, lon_deg: float, zoom: int) -> tuple[float, float]:
    """Convert latitude/longitude in degrees to tile float coordinates in Web Mercator."""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = (lon_deg + 180.0) / 360.0 * n
    ytile = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return xtile, ytile

def _determine_zoom(min_lat: float, min_lon: float, max_lat: float, max_lon: float, max_tiles: int = 16) -> int:
    """Calculate the optimal zoom level ensuring total tiles stay under max_tiles limit."""
    for z in range(15, 8, -1):
        x0, y1 = _deg2num(min_lat, min_lon, z)
        x1, y0 = _deg2num(max_lat, max_lon, z)
        x_span = int(math.floor(x1)) - int(math.floor(x0)) + 1
        y_span = int(math.floor(y1)) - int(math.floor(y0)) + 1
        if x_span * y_span <= max_tiles:
            return z
    return 9

# --- Helper for Map Tiles Fetching ---
def _get_cache_path(bbox: tuple[float, float, float, float], resolution: int) -> Path:
    """Generate a deterministic cache path from the bounding box and resolution."""
    rounded_bbox: tuple[float, float, float, float] = tuple(round(v, 5) for v in bbox)
    key_str = f"{rounded_bbox}_{resolution}"
    key = hashlib.md5(key_str.encode()).hexdigest()
    return MAP_CACHE_DIR / f'mesh_{key}.pkl'

def _fetch_single_tile(z: int, x: int, y: int, session: requests.Session, tile_cache_dir: Path) -> tuple[int, int, PIL.Image.Image | None]:
    """Download a single tile with on-disk caching, returning (x, y, Image)."""
    tile_file = tile_cache_dir / f"{z}_{x}_{y}.png"
    if tile_file.exists():
        try:
            with open(tile_file, 'rb') as f:
                img = PIL.Image.open(io.BytesIO(f.read()))
                img.load()
                return x, y, img
        except Exception:
            pass

    url = f"{OSM_TILE_SERVER}/{z}/{x}/{y}.png"
    try:
        resp = session.get(url, headers={'User-Agent': USER_AGENT}, timeout=5)
        if resp.status_code == 200:
            img = PIL.Image.open(io.BytesIO(resp.content))
            img.load()
            try:
                with open(tile_file, 'wb') as f:
                    f.write(resp.content)
            except Exception:
                pass
            return x, y, img
    except Exception as e:
        logger.debug(f"Failed to download tile {z}/{x}/{y}: {e}")
    return x, y, None

def _fetch_tiles_raw(bbox: tuple[float, float, float, float]) -> dict[str, Any] | None:
    """Native OpenStreetMap tile downloader without legacy smopy dependency."""
    try:
        min_lat, min_lon, max_lat, max_lon = bbox
        z = _determine_zoom(min_lat, min_lon, max_lat, max_lon, max_tiles=20)
        
        x0_f, y1_f = _deg2num(min_lat, min_lon, z)
        x1_f, y0_f = _deg2num(max_lat, max_lon, z)

        xmin = int(math.floor(min(x0_f, x1_f)))
        xmax = int(math.floor(max(x0_f, x1_f)))
        ymin = int(math.floor(min(y0_f, y1_f)))
        ymax = int(math.floor(max(y0_f, y1_f)))

        x_count = xmax - xmin + 1
        y_count = ymax - ymin + 1

        logger.info(f"Downloading OSM map tiles: zoom {z}, grid {x_count}x{y_count} ({x_count*y_count} tiles)...")

        tile_cache_dir = MAP_CACHE_DIR / 'tiles'
        tile_cache_dir.mkdir(parents=True, exist_ok=True)

        composite = PIL.Image.new('RGB', (x_count * TILE_SIZE, y_count * TILE_SIZE), (25, 25, 35))
        tasks = []
        for x in range(xmin, xmax + 1):
            for y in range(ymin, ymax + 1):
                tasks.append((z, x, y))

        success_count = 0
        with requests.Session() as s:
            with ThreadPoolExecutor(max_workers=min(len(tasks), 6)) as executor:
                futures = [executor.submit(_fetch_single_tile, tz, tx, ty, s, tile_cache_dir) for tz, tx, ty in tasks]
                for fut in futures:
                    tx, ty, tile_img = fut.result()
                    if tile_img is not None:
                        px = (tx - xmin) * TILE_SIZE
                        py = (ty - ymin) * TILE_SIZE
                        composite.paste(tile_img, (px, py))
                        success_count += 1

        if success_count == 0:
            logger.warning("No OSM tiles could be downloaded (offline).")
            return None

        return {
            'img': composite,
            'xmin': xmin,
            'ymin': ymin,
            'z': z,
            'tilesize': TILE_SIZE,
        }
    except Exception as e:
        logger.error(f"Map download failed: {e}")
        return None



def _compute_grid(w: int, h: int, scale: float, ts: int, xmin: float, ymin: float, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized coordinate grid calculation using NumPy."""
    js = np.arange(w, dtype=np.float32)
    x = (((js * scale) / ts + xmin) / n) * 360.0 - 180.0
    is_arr = np.arange(h, dtype=np.float32)
    lat_rad = np.pi * (1 - 2 * ((is_arr * scale) / ts + ymin) / n)
    y = np.degrees(np.arctan(np.sinh(lat_rad)))
    return x, y


def expand_to_square_bbox(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Expand a bounding box into an isotropic square area on the ground."""
    min_lat, min_lon, max_lat, max_lon = bbox
    center_lat = (min_lat + max_lat) / 2.0
    center_lon = (min_lon + max_lon) / 2.0
    
    # Scale longitude degrees by cos(latitude) so equal degrees map to equal kilometers
    cos_lat = float(max(np.cos(np.radians(center_lat)), 0.01))
    lat_range = max_lat - min_lat
    lon_range_effective = (max_lon - min_lon) * cos_lat
    max_range = max(lat_range, lon_range_effective)
    
    half_lat = max_range / 2.0
    half_lon = (max_range / cos_lat) / 2.0
    return (
        center_lat - half_lat,
        center_lon - half_lon,
        center_lat + half_lat,
        center_lon + half_lon,
    )


@lru_cache(maxsize=4)
def build_map_mesh(bbox: tuple[float, float, float, float], resolution: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[list[float | str]], dict[str, Any] | None]:
    """
    Build a map mesh at the given resolution.
    Caches the FINAL processed mesh (grids + texture) to disk.
    Returns (x_grid, y_grid, z_grid, matrix, cscale, map_data).
    """
    bbox = expand_to_square_bbox(bbox)
    MAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _get_cache_path(bbox, resolution)

    if cache_path.exists():
        logger.info(f"Loading processed map mesh ({resolution}px) from cache...")
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception:
            logger.warning("Cache corrupted, rebuilding...")

    # Not in cache, perform processing
    map_data = _fetch_tiles_raw(bbox)
    
    if map_data is None:
        # Fallback: Create a simple flat neutral grid if offline and no cache
        logger.warning("Offline: creating fallback neutral grid...")
        new_w, new_h = 2, 2
        matrix = np.zeros((new_h, new_w), dtype=int)
        cscale = [[0, 'rgb(30, 30, 45)'], [1, 'rgb(30, 30, 45)']]
        x = np.array([bbox[1], bbox[3]])
        y = np.array([bbox[2], bbox[0]])
        z = np.zeros(matrix.shape)
    else:
        img = map_data['img']
        original_w, original_h = img.size
        n = 2 ** map_data['z']
        ts = map_data['tilesize']

        # 1. Resize & Palette
        scale = max(1, max(original_w, original_h) / resolution)
        new_w, new_h = int(original_w / scale), int(original_h / scale)

        logger.info(f"Processing map mesh: {original_w}x{original_h} -> {new_w}x{new_h}...")
        img_rs = img.resize((new_w, new_h), resample=PIL.Image.Resampling.BILINEAR)
        img_p = img_rs.convert('P', palette=PIL.Image.Palette.ADAPTIVE, colors=PALETTE_COLORS)
        
        matrix = np.array(img_p)
        palette = img_p.getpalette()
        cols = np.array(palette).reshape(-1, 3)[:PALETTE_COLORS]
        cscale = [
            [i / (PALETTE_COLORS - 1), f'rgb({c[0]},{c[1]},{c[2]})']
            for i, c in enumerate(cols)
        ]

        # 2. Grid calculation
        x, y = _compute_grid(new_w, new_h, scale, ts, map_data['xmin'], map_data['ymin'], n)
        z = np.zeros(matrix.shape, dtype=np.float32)

        # Strip raw composite image to free memory and prevent huge cache files
        map_data.pop('img', None)

    result = (x, y, z, matrix, cscale, map_data)


    # 3. Save to cache (only if we have real map data)
    if map_data is not None:
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            logger.error(f"Failed to cache mesh: {e}")

    return result
