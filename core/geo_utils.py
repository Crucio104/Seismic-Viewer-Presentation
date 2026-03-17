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

def _get_cache_path(bbox):
    """Generate a deterministic cache path from the bounding box."""
    key = hashlib.md5(str(bbox).encode()).hexdigest()
    return os.path.join(MAP_CACHE_DIR, f'{key}.pkl')


def _fetch_map_with_cache(bbox):
    """Fetch Smopy tiles, using a local disk cache to skip network on repeat runs."""
    os.makedirs(MAP_CACHE_DIR, exist_ok=True)
    cache_path = _get_cache_path(bbox)

    if os.path.exists(cache_path):
        print("Loading map from local cache...")
        with open(cache_path, 'rb') as f:
            return pickle.load(f)

    print("Downloading map tiles (first time, will be cached)...")
    map_obj = smopy.Map(bbox)
    img = map_obj.to_pil()
    data = {
        'img': img,
        'xmin': map_obj.xmin, 'ymin': map_obj.ymin,
        'z': map_obj.z, 'tilesize': map_obj.tilesize,
    }
    with open(cache_path, 'wb') as f:
        pickle.dump(data, f)
    return data


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
    Returns (x_grid, y_grid, z_grid, surfacecolor, colorscale, map_data).
    """
    map_data = _fetch_map_with_cache(bbox)
    img = map_data['img']
    original_w, original_h = img.size
    n = 2 ** map_data['z']
    ts = map_data['tilesize']

    scale = max(1, max(original_w, original_h) / resolution)
    new_w, new_h = int(original_w / scale), int(original_h / scale)

    img_rs = img.resize((new_w, new_h), resample=PIL.Image.BILINEAR)
    img_p = img_rs.convert('P', palette=PIL.Image.ADAPTIVE, colors=PALETTE_COLORS)
    matrix = np.array(img_p)
    palette = img_p.getpalette()
    cols = np.array(palette).reshape(-1, 3)[:PALETTE_COLORS]
    cscale = [
        [i / (PALETTE_COLORS - 1), f'rgb({c[0]},{c[1]},{c[2]})']
        for i, c in enumerate(cols)
    ]

    x, y = _compute_grid(new_w, new_h, scale, ts, map_data['xmin'], map_data['ymin'], n)
    z = np.zeros(matrix.shape)
    return x, y, z, matrix, cscale, map_data
