from pathlib import Path
import hashlib
import pickle
import numpy as np
import smopy
import urllib.request
import ssl
import PIL.Image
import logging
from functools import lru_cache
from typing import Any
from core.config import PALETTE_COLORS, MAP_CACHE_DIR

logger = logging.getLogger(__name__)

# --- Helper for Map Tiles Fetching ---
def _get_cache_path(bbox: tuple[float, float, float, float], resolution: int) -> Path:
    """Generate a deterministic cache path from the bounding box and resolution."""
    # Round bbox to 5 decimal places to avoid tiny float differences breaking cache
    rounded_bbox: tuple[float, float, float, float] = tuple(round(v, 5) for v in bbox)
    key_str = f"{rounded_bbox}_{resolution}"
    key = hashlib.md5(key_str.encode()).hexdigest()
    return MAP_CACHE_DIR / f'mesh_{key}.pkl'


def _fetch_tiles_raw(bbox: tuple[float, float, float, float]) -> dict[str, Any] | None:
    """Low-level fetch from Smopy with error handling for offline usage."""
    try:
        logger.info(f"Downloading map tiles for area {bbox}...")
        try:
            map_obj = smopy.Map(bbox)
        except (ssl.SSLError, urllib.error.URLError) as ssl_err:
            logger.warning(f"SSL certificate issue downloading tiles ({ssl_err}), retrying with local SSL fallback...")
            ctx = ssl._create_unverified_context() if hasattr(ssl, '_create_unverified_context') else None
            unverified_opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
            unverified_opener.addheaders = [('User-Agent', 'SeismicViewer/1.0')]
            orig_opener = urllib.request._opener
            urllib.request.install_opener(unverified_opener)
            try:
                map_obj = smopy.Map(bbox)
            finally:
                urllib.request.install_opener(orig_opener)

        return {
            'img': map_obj.to_pil(),
            'xmin': map_obj.xmin, 'ymin': map_obj.ymin,
            'z': map_obj.z, 'tilesize': map_obj.tilesize,
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

    result = (x, y, z, matrix, cscale, map_data)


    # 3. Save to cache (only if we have real map data)
    if map_data is not None:
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            logger.error(f"Failed to cache mesh: {e}")

    return result


