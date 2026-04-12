import os
import hashlib
import pickle
import numpy as np
import smopy
import PIL.Image

MESH_HD_SIZE = 700
MESH_LOW_SIZE = 200
PALETTE_COLORS = 128

MAP_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'resources', '.map_cache'
)

def _get_cache_path(bbox, resolution):
    """Generate a deterministic cache path from the bounding box and resolution."""
    # Round bbox to 5 decimal places to avoid tiny float differences breaking cache
    rounded_bbox = tuple(round(v, 5) for v in bbox)
    key_str = f"{rounded_bbox}_{resolution}"
    key = hashlib.md5(key_str.encode()).hexdigest()
    return os.path.join(MAP_CACHE_DIR, f'mesh_{key}.pkl')


def _fetch_tiles_raw(bbox):
    """Low-level fetch from Smopy. Tiles themselves are cached by smopy/os common patterns, 
    but we keep this clean here.
    """
    print("Downloading map tiles (first time for this area)...")
    map_obj = smopy.Map(bbox)
    return {
        'img': map_obj.to_pil(),
        'xmin': map_obj.xmin, 'ymin': map_obj.ymin,
        'z': map_obj.z, 'tilesize': map_obj.tilesize,
    }


def _compute_grid(w, h, scale, ts, xmin, ymin, n):
    """Vectorized coordinate grid calculation using NumPy."""
    js = np.arange(w)
    x = (((js * scale) / ts + xmin) / n) * 360.0 - 180.0
    is_arr = np.arange(h)
    lat_rad = np.pi * (1 - 2 * ((is_arr * scale) / ts + ymin) / n)
    y = np.degrees(np.arctan(np.sinh(lat_rad)))
    return x, y


def build_map_mesh(bbox, resolution):
    """
    Build a map mesh at the given resolution.
    Caches the FINAL processed mesh (grids + texture) to disk.
    Returns (x_grid, y_grid, z_grid, matrix, cscale, map_data).
    """
    os.makedirs(MAP_CACHE_DIR, exist_ok=True)
    cache_path = _get_cache_path(bbox, resolution)

    if os.path.exists(cache_path):
        print(f"Loading processed map mesh ({resolution}px) from cache...")
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception:
            print("Cache corrupted, rebuilding...")

    # Not in cache, perform processing
    map_data = _fetch_tiles_raw(bbox)
    img = map_data['img']
    original_w, original_h = img.size
    n = 2 ** map_data['z']
    ts = map_data['tilesize']

    # 1. Resize & Palette
    scale = max(1, max(original_w, original_h) / resolution)
    new_w, new_h = int(original_w / scale), int(original_h / scale)

    print(f"Processing map mesh: {original_w}x{original_h} -> {new_w}x{new_h}...")
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
    z = np.zeros(matrix.shape)

    result = (x, y, z, matrix, cscale, map_data)

    # 3. Save to cache
    try:
        with open(cache_path, 'wb') as f:
            pickle.dump(result, f)
    except Exception as e:
        print(f"Failed to cache mesh: {e}")

    return result

