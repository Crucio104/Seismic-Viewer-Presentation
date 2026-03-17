import plotly.graph_objects as go
import csv
import numpy as np
import smopy
import PIL.Image
import hashlib
import pickle
from datetime import datetime
import pandas as pd
import os


# ─── Constants ───────────────────────────────────────────────────────
MIN_MAGNITUDE = 0.5
ANIMATION_BASE_DURATION_MS = 1000
PALETTE_COLORS = 128
MESH_HD_SIZE = 700
MESH_LOW_SIZE = 200
MAP_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'resources', '.map_cache'
)

# ─── Helpers ─────────────────────────────────────────────────────────

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


def _build_map_mesh(bbox, resolution):
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


def _make_hover(df_subset):
    """Generate descriptive hover text strings from a DataFrame subset."""
    return [
        f"Date: {t}<br>"
        f"Magnitude: {m}<br>"
        f"Latitude: {la:.4f}<br>"
        f"Longitude: {lo:.4f}<br>"
        f"Depth: {abs(d):.2f} km"
        for t, m, la, lo, d in zip(
            df_subset['time_str'], df_subset['mag'],
            df_subset['lat'], df_subset['lon'], df_subset['dep']
        )
    ]


# ─── CSV Loading ─────────────────────────────────────────────────────

def load_csv(source_file):
    """Parse a seismic CSV and return extracted data arrays.

    Returns a dict with keys: latitude, longitude, depth, magnitude, times,
    and a summary dict with event_count, date_range.
    Raises ValueError if the CSV is invalid or has no qualifying events.
    """
    with open(source_file, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        header = next(reader)
        # Basic validation: need at least 6 columns
        if len(header) < 6:
            raise ValueError(
                "The CSV must have at least 6 columns "
                "(EventID, Time, Latitude, Longitude, Depth, Magnitude)."
            )
        earthquakes = [
            row for row in reader
            if (len(row) > 5
                and all(row[i] != '' for i in [2, 3, 4, 5])
                and float(row[5]) >= MIN_MAGNITUDE)
        ]
    if not earthquakes:
        raise ValueError(
            f"No seismic events found with M ≥ {MIN_MAGNITUDE}."
        )

    latitude = [float(e[2]) for e in earthquakes]
    longitude = [float(e[3]) for e in earthquakes]
    depth = [-float(e[4]) for e in earthquakes]
    magnitude = [float(e[5]) for e in earthquakes]
    times = [e[1] for e in earthquakes]

    date_range = f"{times[-1][:10]} → {times[0][:10]}"
    print(f"Loaded {len(earthquakes)} seismic events (M ≥ {MIN_MAGNITUDE}).")

    return {
        'latitude': latitude,
        'longitude': longitude,
        'depth': depth,
        'magnitude': magnitude,
        'times': times,
        'summary': {
            'event_count': len(earthquakes),
            'date_range': date_range,
        },
    }


# ─── HTML Generation ─────────────────────────────────────────────────

def generate_html(fig, is_animated=False, back_button=True, earthquake_data=None):
    """Convert a Plotly figure to a full HTML string with custom overlays.

    *earthquake_data*: optional dict with seismic events for client-side filtering.
    """
    html_content = fig.to_html(
        full_html=True,
        include_plotlyjs='cdn',
        config={'scrollZoom': True, 'displayModeBar': False}
    )

    extra_scripts = ""

    # Common Styles (Light Glass Theme)
    extra_scripts += """
    <style>
    :root { 
        /* Slightly more opaque glass and darker border for better contrast on white backgrounds */
        --glass: rgba(15, 12, 41, 0.4); 
        --glass-border: rgba(255, 255, 255, 0.3); 
    }
    body { background: #0f0c29; font-family: 'Segoe UI', system-ui, sans-serif; }

    .glass-panel {
        background: var(--glass); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--glass-border); border-radius: 12px;
        color: #fff; box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        /* Subtle text shadow for legibility on white backgrounds */
        text-shadow: 0 1px 3px rgba(0,0,0,0.8);
    }

    /* Hub Button */
    #back-btn {
        position: fixed; top: 16px; left: 16px; z-index: 100000;
        padding: 10px 20px; font-weight: 600; cursor: pointer;
        transition: all 0.2s;
    }
    #back-btn:hover { border-color: #fff; transform: translateY(-1px); }

    /* Loading Overlay */
    #loader {
        position: fixed; inset: 0; z-index: 200000;
        background: rgba(15, 12, 41, 0.7); backdrop-filter: blur(8px);
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        transition: opacity 0.4s; pointer-events: none; opacity: 0;
    }
    #loader.show { opacity: 1; pointer-events: auto; }
    .spinner {
        width: 50px; height: 50px; border: 4px solid rgba(255,255,255,0.1);
        border-top-color: #fff; border-radius: 50%; animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Filter Bar (Top Center) */
    #filter-bar {
        position: fixed; top: 16px; left: 50%; transform: translateX(-50%); z-index: 99999;
        display: flex; align-items: center; gap: 12px; padding: 8px 20px;
        font-size: 13px;
    }
    #filter-bar input {
        background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.3);
        color: #fff; border-radius: 6px; padding: 4px 8px; cursor: pointer;
        text-shadow: 0 1px 2px rgba(0,0,0,0.6);
    }
    #filter-bar input::-webkit-calendar-picker-indicator { filter: invert(1); }

    /* Playback Bar (Bottom Center) */
    #playback-bar {
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); z-index: 99999;
        display: flex; align-items: center; gap: 20px; padding: 12px 24px;
        width: 80%; max-width: 900px;
    }
    .play-controls { display: flex; gap: 10px; flex-shrink: 0; }
    .play-controls button {
        background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);
        color: #fff; border-radius: 8px; width: 44px; height: 44px;
        display: flex; align-items: center; justify-content: center;
        cursor: pointer; font-size: 18px; transition: all 0.2s;
        text-shadow: 0 1px 4px rgba(0,0,0,0.8);
    }
    .play-controls button:hover { background: rgba(255,255,255,0.2); }
    .play-controls button.active { background: rgba(255,255,255,0.15); border-color: #fff; }

    .slider-container { flex-grow: 1; display: flex; flex-direction: column; gap: 4px; }
    #time-slider {
        width: 100%; height: 6px; border-radius: 3px; background: rgba(255,255,255,0.2);
        outline: none; -webkit-appearance: none; cursor: pointer;
    }
    #time-slider::-webkit-slider-thumb {
        -webkit-appearance: none; width: 16px; height: 16px; border-radius: 50%;
        background: #fff; box-shadow: 0 0 10px rgba(0,0,0,0.5);
    }
    #current-date { font-size: 12px; color: #fff; text-align: center; font-weight: 500; }

    /* Settings Bar (Top Left, under Hub) */
    #settings-bar {
        position: fixed; top: 76px; left: 16px; z-index: 99999;
        display: flex; flex-direction: column; gap: 10px; padding: 12px;
    }
    #settings-bar .label { 
        font-size: 11px; color: #fff; text-transform: uppercase; letter-spacing: 0.5px; 
        font-weight: 700; opacity: 0.9;
    }

    /* Hide Plotly native items */
    .modebar { display: none !important; }
    </style>

    <div id="loader"><div class="spinner"></div><p style="color:#fff;margin-top:15px;font-size:14px">Loading...</p></div>
    <button id="back-btn" class="glass-panel" onclick="pywebview.api.go_back()">← Hub</button>
    """

    if is_animated:
        extra_scripts += """
        <div id="playback-bar" class="glass-panel">
            <div class="play-controls">
                <button id="play-btn">▶</button>
                <button id="pause-btn" class="active">⏸</button>
            </div>
            <div class="slider-container">
                <input type="range" id="time-slider" min="0" max="100" value="0">
                <div id="current-date">Select date</div>
            </div>
        </div>

        <div id="settings-bar" class="glass-panel">
            <div class="settings-group">
                <div class="label">Speed</div>
                <button class="settings-btn" id="speed-toggle">1x (1s/f) ▾</button>
                <div class="glass-panel glass-menu" id="speed-menu">
                    <div class="menu-item active" data-val="1">1x (1s/f)</div>
                    <div class="menu-item" data-val="2">2x</div>
                    <div class="menu-item" data-val="4">4x</div>
                    <div class="menu-item" data-val="8">8x</div>
                    <div class="menu-item" data-val="16">16x</div>
                    <div class="menu-item" data-val="32">32x (32fps)</div>
                </div>
            </div>
            <div class="settings-group" style="margin-top:12px">
                <div class="label">Coloring</div>
                <button class="settings-btn" id="color-toggle">Magnitude ▾</button>
                <div class="glass-panel glass-menu" id="color-menu">
                    <div class="menu-item active" data-mode="mag">Magnitude</div>
                    <div class="menu-item" data-mode="date">Date</div>
                </div>
            </div>
        </div>

        <style>
        .settings-group { position: relative; }
        .settings-btn {
            background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
            color: #fff; border-radius: 8px; padding: 8px 14px; cursor: pointer;
            width: 140px; text-align: left; font-size: 13px; margin-top: 4px;
            transition: all 0.2s; text-shadow: 0 1px 2px rgba(0,0,0,0.5);
            display: flex; justify-content: space-between; align-items: center;
        }
        .settings-btn:hover { background: rgba(255,255,255,0.15); }
        
        .glass-menu {
            position: absolute; left: calc(100% + 15px); top: 0;
            display: none; flex-direction: column; gap: 2px; padding: 6px;
            min-width: 140px; z-index: 100001;
            box-shadow: 10px 0 30px rgba(0,0,0,0.5);
        }
        .glass-menu.show { display: flex; }
        .menu-item {
            padding: 8px 12px; border-radius: 6px; cursor: pointer;
            font-size: 13px; transition: background 0.2s; white-space: nowrap;
        }
        .menu-item:hover { background: rgba(255,255,255,0.12); }
        .menu-item.active { background: rgba(255,255,255,0.22); font-weight: 600; }
        </style>

        <script>
        window.addEventListener('load', function() {
            const gd = document.querySelector('.plotly-graph-div');
            const playBtn = document.getElementById('play-btn');
            const pauseBtn = document.getElementById('pause-btn');
            const slider = document.getElementById('time-slider');
            const dateDisplay = document.getElementById('current-date');

            // Settings buttons & menus
            const speedToggle = document.getElementById('speed-toggle');
            const speedMenu = document.getElementById('speed-menu');
            const colorToggle = document.getElementById('color-toggle');
            const colorMenu = document.getElementById('color-menu');

            let isPlaying = false;
            let currentDuration = """ + str(ANIMATION_BASE_DURATION_MS) + """;

            function showLoading(show) {
                document.getElementById('loader').classList.toggle('show', show);
            }

            // Custom Menu Logic
            speedToggle.onclick = (e) => {
                e.stopPropagation();
                colorMenu.classList.remove('show');
                speedMenu.classList.toggle('show');
            };
            colorToggle.onclick = (e) => {
                e.stopPropagation();
                speedMenu.classList.remove('show');
                colorMenu.classList.toggle('show');
            };
            document.onclick = () => {
                speedMenu.classList.remove('show');
                colorMenu.classList.remove('show');
            };

            speedMenu.querySelectorAll('.menu-item').forEach(item => {
                item.onclick = () => {
                    const mult = parseInt(item.dataset.val);
                    currentDuration = """ + str(ANIMATION_BASE_DURATION_MS) + """ / mult;
                    
                    speedMenu.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    speedToggle.textContent = item.textContent + ' ▾';
                    speedMenu.classList.remove('show');

                    // If playing, restart animation with new duration
                    if (isPlaying) playBtn.click();
                };
            });

            colorMenu.querySelectorAll('.menu-item').forEach(item => {
                item.onclick = () => {
                    const mode = item.dataset.mode;
                    const isMag = (mode === 'mag');
                    
                    Plotly.restyle(gd, {visible: [null, null, isMag, !isMag]}, [0, 1, 2, 3]);

                    colorMenu.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    colorToggle.textContent = item.textContent + ' ▾';
                    colorMenu.classList.remove('show');
                };
            });

            // Sync slider with Plotly
            const steps = gd._fullLayout.sliders[0].steps;
            slider.max = steps.length - 1;
            updateUI(0);

            function updateUI(stepIdx) {
                const step = steps[stepIdx];
                dateDisplay.textContent = "Date: " + step.label;
                slider.value = stepIdx;
            }

            slider.addEventListener('input', () => {
                const idx = parseInt(slider.value);
                updateUI(idx);
                Plotly.animate(gd, [steps[idx].label], {
                    frame: {duration: 0, redraw: true},
                    mode: 'immediate',
                    transition: {duration: 0}
                });
            });

            playBtn.addEventListener('click', () => {
                isPlaying = true;
                playBtn.classList.add('active');
                pauseBtn.classList.remove('active');
                Plotly.restyle(gd, {visible: [true, false]}, [0, 1]); // Low-res
                Plotly.animate(gd, null, {
                    frame: {duration: currentDuration, redraw: true},
                    fromcurrent: true,
                    transition: {duration: 0}
                });
            });

            pauseBtn.addEventListener('click', () => {
                isPlaying = false;
                pauseBtn.classList.add('active');
                playBtn.classList.remove('active');
                Plotly.animate(gd, [null], {mode: 'immediate'});
                Plotly.restyle(gd, {visible: [false, true]}, [0, 1]); // High-res
            });

            gd.on('plotly_animatingframe', (event) => {
                const idx = steps.findIndex(s => s.label === event.name);
                if (idx !== -1) {
                    updateUI(idx);
                    // If it's the last frame, restore High-Res and end isPlaying
                    if (idx === steps.length - 1) {
                        Plotly.restyle(gd, {visible: [false, true]}, [0, 1]);
                        isPlaying = false;
                        playBtn.classList.remove('active');
                        pauseBtn.classList.add('active');
                    }
                }
            });

            gd.on('plotly_animated', () => {
                const activeIdx = gd._fullLayout.sliders[0].active;
                updateUI(activeIdx);
            });
        });
        </script>
        """
    elif earthquake_data:
        # Static View (2D or 3D) with filtering and Color Toggle
        import json
        quakes_json = json.dumps(earthquake_data)
        extra_scripts += """
        <div id="settings-bar" class="glass-panel">
            <div class="settings-group">
                <div class="label">Coloring</div>
                <button class="settings-btn" id="color-toggle">Magnitude ▾</button>
                <div class="glass-panel glass-menu" id="color-menu">
                    <div class="menu-item active" data-mode="mag">Magnitude</div>
                    <div class="menu-item" data-mode="date">Date</div>
                </div>
            </div>
        </div>

        <div id="filter-bar" class="glass-panel">
            <span>Period:</span>
            <input type="date" id="filter-start">
            <span>to</span>
            <input type="date" id="filter-end">
        </div>

        <style>
        .settings-group { position: relative; }
        .settings-btn {
            background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
            color: #fff; border-radius: 8px; padding: 8px 14px; cursor: pointer;
            width: 140px; text-align: left; font-size: 13px; margin-top: 4px;
            transition: all 0.2s; text-shadow: 0 1px 2px rgba(0,0,0,0.5);
            display: flex; justify-content: space-between; align-items: center;
        }
        .settings-btn:hover { background: rgba(255,255,255,0.15); }
        .glass-menu {
            position: absolute; left: calc(100% + 15px); top: 0;
            display: none; flex-direction: column; gap: 2px; padding: 6px;
            min-width: 140px; z-index: 100001;
            box-shadow: 10px 0 30px rgba(0,0,0,0.5);
        }
        .glass-menu.show { display: flex; }
        .menu-item {
            padding: 8px 12px; border-radius: 6px; cursor: pointer;
            font-size: 13px; transition: background 0.2s; white-space: nowrap;
        }
        .menu-item:hover { background: rgba(255,255,255,0.12); }
        .menu-item.active { background: rgba(255,255,255,0.22); font-weight: 600; }
        </style>

        <script>
        const quakeData = """ + quakes_json + """;
        window.addEventListener('load', function() {
            const gd = document.querySelector('.plotly-graph-div');
            const startInput = document.getElementById('filter-start');
            const endInput = document.getElementById('filter-end');
            const colorToggle = document.getElementById('color-toggle');
            const colorMenu = document.getElementById('color-menu');

            const dates = quakeData.times.map(t => t.slice(0, 10));
            const uniqueDates = Array.from(new Set(dates)).sort();

            startInput.min = endInput.min = uniqueDates[0];
            startInput.max = endInput.max = uniqueDates[uniqueDates.length - 1];
            startInput.value = uniqueDates[0];
            endInput.value = uniqueDates[uniqueDates.length - 1];

            // Global limits for consistent coloring
            const magMin = Math.min(...quakeData.magnitude);
            const magMax = Math.max(...quakeData.magnitude);
            const dnumMin = Math.min(...quakeData.dates_num);
            const dnumMax = Math.max(...quakeData.dates_num);

            let currentColorMode = 'mag';

            // Menu logic
            colorToggle.onclick = (e) => {
                e.stopPropagation();
                colorMenu.classList.toggle('show');
            };
            document.onclick = () => colorMenu.classList.remove('show');

            colorMenu.querySelectorAll('.menu-item').forEach(item => {
                item.onclick = () => {
                    const mode = item.dataset.mode;
                    currentColorMode = mode;
                    const isMag = (mode === 'mag');

                    colorMenu.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    colorToggle.textContent = item.textContent + ' ▾';
                    
                    applyFilter(); // Re-apply current filter with new color mode
                };
            });

            function applyFilter() {
                const start = startInput.value;
                const end = endInput.value;
                document.getElementById('loader').classList.add('show');

                setTimeout(() => {
                    const indices = [];
                    for (let i = 0; i < dates.length; i++) {
                        if (dates[i] >= start && dates[i] <= end) indices.push(i);
                    }

                    const filtered = {
                        lon: indices.map(i => quakeData.longitude[i]),
                        lat: indices.map(i => quakeData.latitude[i]),
                        mag: indices.map(i => quakeData.magnitude[i]),
                        dep: indices.map(i => quakeData.depth[i]),
                        times: indices.map(i => quakeData.times[i]),
                        dnum: indices.map(i => quakeData.dates_num[i])
                    };

                    const is3D = (gd.layout.scene !== undefined);
                    const isMag = (currentColorMode === 'mag');

                    if (is3D) {
                        // 3D Static: Toggle between Trace 1 (Mag) and Trace 2 (Date)
                        Plotly.restyle(gd, {
                            x: [filtered.lon],
                            y: [filtered.lat],
                            z: [filtered.dep],
                            'marker.size': [filtered.mag],
                            'marker.color': [isMag ? filtered.mag : filtered.dnum],
                            'marker.cmin': [isMag ? magMin : dnumMin],
                            'marker.cmax': [isMag ? magMax : dnumMax],
                            hovertext: [filtered.times],
                            hovertemplate: '%{hovertext}<extra></extra>',
                            visible: isMag
                        }, [1]);
                        
                        Plotly.restyle(gd, {
                            x: [filtered.lon],
                            y: [filtered.lat],
                            z: [filtered.dep],
                            'marker.size': [filtered.mag],
                            'marker.color': [isMag ? filtered.mag : filtered.dnum],
                            'marker.cmin': [isMag ? magMin : dnumMin],
                            'marker.cmax': [isMag ? magMax : dnumMax],
                            hovertext: [filtered.times],
                            hovertemplate: '%{hovertext}<extra></extra>',
                            visible: !isMag
                        }, [2]);
                    } else {
                        // 2D Map: Update single trace (index 0)
                        Plotly.restyle(gd, {
                            lat: [filtered.lat],
                            lon: [filtered.lon],
                            'marker.size': [filtered.mag],
                            'marker.color': [isMag ? filtered.mag : filtered.dnum],
                            'marker.cmax': [isMag ? magMax : dnumMax],
                            'marker.colorscale': isMag ? 'Plasma' : 'Turbo',
                            'marker.colorbar.title': isMag ? 'Magnitude' : 'Days',
                            hovertext: [filtered.times],
                            hovertemplate: '%{hovertext}<extra></extra>'
                        }, [0]);
                    }

                    document.getElementById('loader').classList.remove('show');
                }, 100);
            }

            startInput.onchange = endInput.onchange = applyFilter;
        });
        </script>
        """

    if extra_scripts:
        html_content = html_content.replace('</body>', extra_scripts + '</body>')

    return html_content


# ─── View Functions ──────────────────────────────────────────────────

def view_2d(longitude, latitude, magnitude, times, dates_num=None):
    import plotly.express as px
    import pandas as pd
    
    # Create hover text using the helper
    hover_df = pd.DataFrame({
        'lon': longitude, 'lat': latitude,
        'mag': magnitude, 'dep': [0]*len(longitude), 
        'time_str': times
    })
    all_hover = _make_hover(hover_df)

    # Use px for its excellent bubble size scaling, but avoid using 'color' argument
    # which forces global coloraxis. Instead, we'll set color at the trace level.
    fig = px.scatter_mapbox(
        lat=latitude, lon=longitude,
        size=magnitude,
        hover_name=all_hover,
        zoom=12,
        labels={"lat": "Latitude", "lon": "Longitude", "size": "Magnitude"},
    )
    
    # Configure coloring and colorbar at the trace level
    fig.update_traces(
        marker=dict(
            color=magnitude,
            colorscale='Plasma',
            showscale=True,
            colorbar=dict(title="Magnitude", x=1.02, thickness=15, len=0.5)
        ),
        hoverinfo='text',
        hovertemplate='%{hovertext}<extra></extra>'
    )
    
    # Add custom numerical date data for client-side restyling
    if dates_num is not None:
        fig.data[0].customdata = np.array(dates_num).reshape(-1, 1)

    fig.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0}
    )
    return fig


def view_3d(longitude, latitude, magnitude, depth, times, dates_num=None):
    min_lon, max_lon = min(longitude), max(longitude)
    min_lat, max_lat = min(latitude), max(latitude)
    min_depth = min(depth)
    bbox = (min_lat, min_lon, max_lat, max_lon)

    print("Preparing 3D static view...")
    x_grid, y_grid, z_grid, surfacecolor, colorscale, _ = _build_map_mesh(
        bbox, MESH_HD_SIZE
    )

    # Prepare hover text
    hover_df = pd.DataFrame({
        'lon': longitude, 'lat': latitude,
        'mag': magnitude, 'dep': depth, 
        'time_str': times
    })
    all_hover = _make_hover(hover_df)

    fig = go.Figure()
    # Trace 0: Map Surface
    fig.add_trace(go.Surface(
        x=x_grid, y=y_grid, z=z_grid,
        surfacecolor=surfacecolor, colorscale=colorscale,
        showscale=False, opacity=0.9, hoverinfo='skip'
    ))

    # Trace 1: Earthquakes (Magnitude Coloring)
    fig.add_trace(go.Scatter3d(
        x=longitude, y=latitude, z=depth,
        mode='markers', hovertext=all_hover,
        marker=dict(
            size=magnitude, sizemode='diameter', sizeref=0.2,
            color=magnitude, colorscale='Plasma',
            showscale=True,
            colorbar=dict(title="Magnitude", x=1.02, thickness=15, len=0.5),
            line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
            opacity=0.8,
        ),
        name='Earthquakes (Mag)', visible=True,
        hovertemplate='%{hovertext}<extra></extra>'
    ))

    # Trace 2: Earthquakes (Date Coloring)
    if dates_num is not None:
        fig.add_trace(go.Scatter3d(
            x=longitude, y=latitude, z=depth,
            mode='markers', hovertext=all_hover,
            marker=dict(
                size=magnitude, sizemode='diameter', sizeref=0.2,
                color=dates_num, colorscale='Turbo',
                showscale=True,
                colorbar=dict(title="Days", x=1.02, thickness=15, len=0.5),
                line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
                opacity=0.8,
            ),
            name='Earthquakes (Date)', visible=False,
            hovertemplate='%{hovertext}<extra></extra>'
        ))

    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Longitude', range=[x_grid[0], x_grid[-1]]),
            yaxis=dict(title='Latitude', range=[y_grid[-1], y_grid[0]]),
            zaxis=dict(title='Depth (km)', range=[min_depth, 0]),
            aspectmode='manual',
            aspectratio=dict(x=1, y=1, z=0.5),
        ),
        margin=dict(l=0, r=0, b=0, t=30),
    )
    return fig


def get_3d_animated_figure(longitude, latitude, magnitude, depth, times,
                           on_progress=None):
    def _report(msg):
        print(msg)
        if on_progress:
            on_progress(msg)

    _report("Preparing 3D animation data...")
    df = pd.DataFrame({
        'lon': longitude, 'lat': latitude,
        'mag': magnitude, 'dep': depth, 'time_str': times,
        'time': [
            datetime.strptime(t, "%Y-%m-%d %H:%M:%S.%f")
            if '.' in t
            else datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
            for t in times
        ],
    })

    df['date_num'] = (df['time'] - df['time'].min()).dt.total_seconds() / 86400.0
    df = df.sort_values('time').reset_index(drop=True)
    df['date'] = df['time'].dt.strftime('%Y-%m-%d')
    unique_dates = sorted(df['date'].unique())

    bbox = (df['lat'].min(), df['lon'].min(), df['lat'].max(), df['lon'].max())
    min_depth = df['dep'].min()

    # Build dual-resolution meshes
    _report("Building map mesh (HD + SD)...")
    x_high, y_high, z_high, mat_high, scale_high, map_data = _build_map_mesh(
        bbox, MESH_HD_SIZE
    )

    # Low-res derived from high-res (fast nearest-neighbor)
    n = 2 ** map_data['z']
    ts = map_data['tilesize']
    scale_hd = max(1, max(map_data['img'].size) / MESH_HD_SIZE)
    scale_ratio = MESH_HD_SIZE / MESH_LOW_SIZE
    new_w_low = int(len(x_high) / scale_ratio)
    new_h_low = int(len(y_high) / scale_ratio)
    mat_low = np.array(
        PIL.Image.fromarray(mat_high).resize(
            (new_w_low, new_h_low), resample=PIL.Image.NEAREST
        )
    )
    scale_low = scale_high
    x_low, y_low = _compute_grid(
        new_w_low, new_h_low, scale_hd * scale_ratio,
        ts, map_data['xmin'], map_data['ymin'], n
    )
    z_low = np.zeros(mat_low.shape)

    mag_min, mag_max = df['mag'].min(), df['mag'].max()
    date_n_min, date_n_max = df['date_num'].min(), df['date_num'].max()

    # Start with no dots — animation begins empty
    initial_df = df.iloc[:0]  # empty DataFrame
    initial_hover = []
    fig = go.Figure()

    # Trace 0: Low-Res Surface (Play)
    fig.add_trace(go.Surface(
        x=x_low, y=y_low, z=z_low,
        surfacecolor=mat_low, colorscale=scale_low,
        showscale=False, opacity=0.9, hoverinfo='skip', visible=False,
        lighting=dict(ambient=1, diffuse=0, specular=0, roughness=1, fresnel=0),
        contours=dict(
            x=dict(show=False), y=dict(show=False), z=dict(show=False)
        ),
    ))
    # Trace 1: High-Res Surface (Pause/Static)
    fig.add_trace(go.Surface(
        x=x_high, y=y_high, z=z_high,
        surfacecolor=mat_high, colorscale=scale_high,
        showscale=False, opacity=0.9, hoverinfo='skip', visible=True,
        lighting=dict(ambient=1, diffuse=0, specular=0, roughness=1, fresnel=0),
        contours=dict(
            x=dict(show=False), y=dict(show=False), z=dict(show=False)
        ),
    ))
    # Trace 2: Magnitude coloring
    fig.add_trace(go.Scatter3d(
        x=initial_df['lon'], y=initial_df['lat'], z=initial_df['dep'],
        mode='markers', hovertext=initial_hover, hoverinfo='text',
        marker=dict(
            size=initial_df['mag'], sizemode='diameter', sizeref=0.1,
            color=initial_df['mag'], colorscale='Plasma',
            showscale=True, cmin=mag_min, cmax=mag_max,
            colorbar=dict(title="Magnitude", x=1.02, thickness=15, len=0.4),
            line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
            opacity=0.8,
        ),
        name='Color: Magnitude', visible=True,
    ))
    # Trace 3: Date coloring
    fig.add_trace(go.Scatter3d(
        x=initial_df['lon'], y=initial_df['lat'], z=initial_df['dep'],
        mode='markers', hovertext=initial_hover, hoverinfo='text',
        marker=dict(
            size=initial_df['mag'], sizemode='diameter', sizeref=0.1,
            color=initial_df['date_num'], colorscale='Turbo',
            showscale=True, cmin=date_n_min, cmax=date_n_max,
            colorbar=dict(title="Days", x=1.02, thickness=15, len=0.4),
            line=dict(width=1, color='rgba(50, 50, 50, 0.8)'),
            opacity=0.8,
        ),
        name='Color: Date', visible=False,
        hovertemplate='%{hovertext}<extra></extra>'
    ))

    # ── Optimized frame generation ───────────────────────────────────
    # Pre-compute all hover texts and extract arrays once.
    # Use cumulative slicing (O(n) total) instead of rebuilding
    # hover texts for the entire cumulative subset each frame (O(n²)).
    _report("Generating animation frames...")
    all_hover = _make_hover(df)
    arr_lon = df['lon'].values
    arr_lat = df['lat'].values
    arr_dep = df['dep'].values
    arr_mag = df['mag'].values
    arr_dnum = df['date_num'].values
    date_counts = df.groupby('date').size()

    frames = []
    cum = 0
    n_dates = len(unique_dates)

    for i, date in enumerate(unique_dates):
        cum += date_counts[date]

        frames.append(go.Frame(
            data=[
                go.Scatter3d(
                    x=arr_lon[:cum], y=arr_lat[:cum], z=arr_dep[:cum],
                    hovertext=all_hover[:cum],
                    marker=dict(
                        size=arr_mag[:cum], color=arr_mag[:cum],
                        cmin=mag_min, cmax=mag_max,
                    ),
                    hovertemplate='%{hovertext}<extra></extra>'
                ),
                go.Scatter3d(
                    x=arr_lon[:cum], y=arr_lat[:cum], z=arr_dep[:cum],
                    hovertext=all_hover[:cum],
                    marker=dict(
                        size=arr_mag[:cum], color=arr_dnum[:cum],
                        cmin=date_n_min, cmax=date_n_max, colorscale='Turbo',
                    ),
                    hovertemplate='%{hovertext}<extra></extra>'
                ),
            ],
            traces=[2, 3], name=date,
        ))

        if (i + 1) % 30 == 0 or i == n_dates - 1:
            _report(f"Frames: {i + 1}/{n_dates}")

    fig.frames = frames

    dur = ANIMATION_BASE_DURATION_MS
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Longitude', range=[x_low[0], x_low[-1]]),
            yaxis=dict(title='Latitude', range=[y_low[-1], y_low[0]]),
            zaxis=dict(title='Depth (km)', range=[min_depth, 0]),
            aspectmode='manual', aspectratio=dict(x=1, y=1, z=0.5),
            camera=dict(
                center=dict(x=0, y=0, z=0),
                eye=dict(x=1.5, y=1.5, z=1.5),
            ),
        ),
        updatemenus=[],
        sliders=[{
            "active": 0, "visible": False, # Hidden, synced via JS to our custom slider
            "steps": [
                {
                    "args": [
                        [date],
                        {"frame": {"duration": 0, "redraw": True},
                         "mode": "immediate",
                         "transition": {"duration": 0}},
                    ],
                    "label": date, "method": "animate",
                }
                for date in unique_dates
            ],
        }],
        margin=dict(l=0, r=80, b=0, t=30),
    )

    return fig


# ─── Build Visualization ─────────────────────────────────────────────

def build_view_html(data, view_style, back_button=True, on_progress=None):
    """Build a visualization HTML string from pre-loaded *data* dict.

    *view_style*: 0 = 2D, 1 = 3D static, 2 = 3D animated.
    *on_progress*: optional callback(msg) for progress reporting.
    Returns the HTML string.
    """
    def _report(msg):
        if on_progress:
            on_progress(msg)

    lon = data['longitude']
    lat = data['latitude']
    mag = data['magnitude']
    dep = data['depth']
    times = data['times']

    # Pre-calculate numerical dates for color scaling in static views
    def _get_dates_num():
        ts = [
            datetime.strptime(t, "%Y-%m-%d %H:%M:%S.%f") if '.' in t
            else datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
            for t in times
        ]
        min_t = min(ts)
        return [(t - min_t).total_seconds() / 86400.0 for t in ts]

    if view_style == 0:
        _report("Generating 2D map…")
        d_num = _get_dates_num()
        fig = view_2d(lon, lat, mag, times, dates_num=d_num)
        _report("Rendering HTML…")
        # For 2D, we pass depth as 0s so the filtering JS knows it's 2D
        static_data = data.copy()
        static_data['depth'] = [0] * len(lon)
        static_data['dates_num'] = d_num
        return generate_html(fig, back_button=back_button, earthquake_data=static_data)
    elif view_style == 1:
        _report("Preparing 3D static view…")
        d_num = _get_dates_num()
        fig = view_3d(lon, lat, mag, dep, times, dates_num=d_num)
        _report("Rendering HTML…")
        static_data = data.copy()
        static_data['dates_num'] = d_num
        return generate_html(fig, back_button=back_button, earthquake_data=static_data)
    elif view_style == 2:
        fig = get_3d_animated_figure(
            lon, lat, mag, dep, times, on_progress=on_progress
        )
        _report("Rendering final HTML…")
        return generate_html(fig, is_animated=True, back_button=back_button)
    else:
        raise ValueError(f"Stile di visualizzazione non valido: {view_style}")