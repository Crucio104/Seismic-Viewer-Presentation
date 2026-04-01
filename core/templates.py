import json

ANIMATION_BASE_DURATION_MS = 1000

def _make_hover(df_subset):
    """Generate descriptive hover text strings from a DataFrame subset."""
    return [
        f"Date: {t}<br>"
        f"Magnitude: {m}<br>"
        f"Latitude: {la:.4f}<br>"
        f"Longitude: {lo:.4f}<br>"
        f"Depth: {abs(d):.4f} km"
        for t, m, la, lo, d in zip(
            df_subset['time_str'], df_subset['mag'],
            df_subset['lat'], df_subset['lon'], df_subset['dep']
        )
    ]

def generate_html(fig, is_animated=False, back_button=True, earthquake_data=None):
    """Convert a Plotly figure to a full HTML string with custom overlays."""
    html_content = fig.to_html(
        full_html=True,
        include_plotlyjs='cdn',
        config={'scrollZoom': True, 'displayModeBar': False}
    )

    extra_scripts = ""

    # Common Styles (Glass Theme)
    extra_scripts += """
    <style>
    :root { 
        --glass: rgba(15, 12, 41, 0.4); 
        --glass-border: rgba(255, 255, 255, 0.2); 
    }
    body { background: #0f0c29; font-family: 'Segoe UI', system-ui, sans-serif; }

    .glass-panel {
        background: var(--glass); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--glass-border); border-radius: 12px;
        color: #fff; box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        text-shadow: 0 1px 3px rgba(0,0,0,0.8);
    }

    #back-btn {
        position: fixed; top: 16px; left: 16px; z-index: 100000;
        padding: 10px 20px; font-weight: 600; cursor: pointer;
        transition: all 0.2s;
    }
    #back-btn:hover { border-color: #fff; transform: translateY(-1px); }

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

    #filter-bar {
        position: fixed; top: 16px; left: 50%; transform: translateX(-50%); z-index: 99999;
        display: flex; align-items: center; gap: 12px; padding: 8px 20px;
        font-size: 13px;
    }
    #filter-bar input {
        background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.3);
        color: #fff; border-radius: 6px; padding: 4px 8px; cursor: pointer;
    }
    #filter-bar input::-webkit-calendar-picker-indicator { filter: invert(1); }

    #settings-bar {
        position: fixed; top: 76px; left: 16px; z-index: 99999;
        display: flex; flex-direction: column; gap: 10px; padding: 12px;
        width: 180px;
    }
    .settings-group { position: relative; width: 100%; }
    .label { 
        font-size: 11px; color: #fff; text-transform: uppercase; letter-spacing: 0.5px; 
        font-weight: 700; opacity: 0.9; margin-bottom: 4px;
    }
    .settings-btn {
        background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
        color: #fff; border-radius: 8px; padding: 10px 14px; cursor: pointer;
        width: 100%; text-align: left; font-size: 13px;
        transition: all 0.2s; display: flex; justify-content: space-between; align-items: center;
        font-family: inherit;
    }
    .settings-btn:hover { background: rgba(255,255,255,0.15); }
    
    .settings-row { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
    .settings-row .glass-input { margin-top: 0; flex: 1; }
    .settings-row .settings-btn { width: auto; padding: 6px 10px; flex-shrink: 0; }
    .glass-menu {
        position: absolute; left: calc(100% + 15px); top: 0;
        display: none; flex-direction: column; gap: 2px; padding: 6px;
        min-width: 140px; z-index: 100001;
        box-shadow: 10px 0 30px rgba(0,0,0,0.5);
        background: var(--glass); backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--glass-border); border-radius: 12px;
    }
    .glass-menu.show { display: flex; }
    .menu-item {
        padding: 8px 12px; border-radius: 6px; cursor: pointer;
        font-size: 13px; transition: background 0.2s;
    }
    .menu-item:hover { background: rgba(255,255,255,0.12); }
    .menu-item.active { background: rgba(255,255,255,0.22); font-weight: 600; }

    .slider {
        width: 100%; height: 6px; appearance: none; background: rgba(255,255,255,0.1);
        border-radius: 3px; outline: none; margin-top: 8px;
    }
    .slider::-webkit-slider-thumb {
        -webkit-appearance: none;
        appearance: none;
        width: 14px; height: 14px; background: #fff; border-radius: 50%; cursor: pointer;
    }

    .glass-input {
        background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.2);
        color: #fff; border-radius: 6px; padding: 6px 10px; width: 100%;
        font-size: 14px; outline: none; margin-top: 6px; font-family: inherit;
        transition: border-color 0.2s;
    }
    .glass-input:focus { border-color: #fff; background: rgba(255,255,255,0.12); }
    /* Hide arrows in Chrome, Safari, Edge, Opera */
    .glass-input::-webkit-outer-spin-button,
    .glass-input::-webkit-inner-spin-button { 
        -webkit-appearance: none; 
        appearance: none;
        margin: 0; 
    }
    /* Hide arrows in Firefox */
    .glass-input[type=number] { 
        -moz-appearance: textfield;
        appearance: textfield; 
    }

    #playback-bar {
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); z-index: 99999;
        display: flex; align-items: center; gap: 20px; padding: 12px 24px;
        width: 80%; max-width: 900px;
    }
    .play-controls { display: flex; gap: 10px; }
    .play-controls button {
        background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);
        color: #fff; border-radius: 8px; width: 44px; height: 44px; cursor: pointer;
        font-size: 18px; transition: all 0.2s;
    }
    .play-controls button.active { border-color: #fff; background: rgba(255,255,255,0.2); }

    .slider-container { flex-grow: 1; display: flex; flex-direction: column; gap: 4px; }
    #time-slider { width: 100%; }
    #current-date { font-size: 12px; color: #fff; text-align: center; }

    #filter-loader {
        position: fixed; inset: 0; z-index: 150000;
        background: rgba(15, 12, 41, 0.4); backdrop-filter: blur(4px);
        display: none; align-items: center; justify-content: center;
        border-radius: 12px;
    }
    #filter-loader.show { display: flex; }

    .modebar { display: none !important; }
    </style>

    <div id="loader"><div class="spinner"></div><p style="color:#fff;margin-top:15px;font-size:14px">Processing dataset...</p></div>
    <button id="back-btn" class="glass-panel" onclick="pywebview.api.go_back()">← Hub</button>
    """

    if is_animated:
        extra_scripts += f"""
        <div id="playback-bar" class="glass-panel">
            <div class="play-controls">
                <button id="play-btn">▶</button>
                <button id="pause-btn" class="active">⏸</button>
            </div>
            <div class="slider-container">
                <input type="range" id="time-slider" class="slider" min="0" max="100" value="0">
                <div id="current-date">Timeline initializing</div>
            </div>
        </div>

        <div id="settings-bar" class="glass-panel">
            <div class="settings-group">
                <div class="label">Playback Speed</div>
                <button class="settings-btn" id="speed-toggle">1x ▾</button>
                <div class="glass-panel glass-menu" id="speed-menu">
                    <div class="menu-item active" data-val="1">1x (Real-time)</div>
                    <div class="menu-item" data-val="4">4x</div>
                    <div class="menu-item" data-val="16">16x</div>
                    <div class="menu-item" data-val="32">32x (Turbo)</div>
                </div>
            </div>
            <div class="settings-group" style="margin-top:12px">
                <div class="label">Color Analysis</div>
                <button class="settings-btn" id="color-toggle">Magnitude ▾</button>
                <div class="glass-panel glass-menu" id="color-menu">
                    <div class="menu-item active" data-mode="mag">Magnitude (Plasma)</div>
                    <div class="menu-item" data-mode="date">Date (Turbo)</div>
                </div>
            </div>
            <div class="settings-group" style="margin-top:12px">
                <div class="label">Go to Date</div>
                <div class="settings-row">
                    <input type="date" id="jump-date" class="glass-input">
                    <button class="settings-btn" id="jump-btn" style="justify-content:center;">Go</button>
                </div>
            </div>
        </div>

        <script>
        window.addEventListener('load', function() {{
            const gd = document.querySelector('.plotly-graph-div');
            const playBtn = document.getElementById('play-btn');
            const pauseBtn = document.getElementById('pause-btn');
            const slider = document.getElementById('time-slider');
            const dateDisplay = document.getElementById('current-date');
            const speedToggle = document.getElementById('speed-toggle');
            const speedMenu = document.getElementById('speed-menu');
            const colorToggle = document.getElementById('color-toggle');
            const colorMenu = document.getElementById('color-menu');

            let isPlaying = false;
            let currentDuration = {ANIMATION_BASE_DURATION_MS};

            speedToggle.onclick = (e) => {{ e.stopPropagation(); colorMenu.classList.remove('show'); speedMenu.classList.toggle('show'); }};
            colorToggle.onclick = (e) => {{ e.stopPropagation(); speedMenu.classList.remove('show'); colorMenu.classList.toggle('show'); }};
            document.onclick = () => {{ speedMenu.classList.remove('show'); colorMenu.classList.remove('show'); }};

            speedMenu.querySelectorAll('.menu-item').forEach(item => {{
                item.onclick = () => {{
                    const mult = parseInt(item.dataset.val);
                    currentDuration = {ANIMATION_BASE_DURATION_MS} / mult;
                    speedMenu.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    speedToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
                    if (isPlaying) playBtn.click();
                }};
            }});

            colorMenu.querySelectorAll('.menu-item').forEach(item => {{
                item.onclick = () => {{
                    const mode = item.dataset.mode;
                    Plotly.restyle(gd, {{visible: [null, null, (mode === 'mag'), (mode !== 'mag')]}}, [0, 1, 2, 3]);
                    colorMenu.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    colorToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
                }};
            }});

            const steps = gd._fullLayout.sliders[0].steps;
            slider.max = steps.length - 1;
            
            function updateUI(stepIdx) {{
                dateDisplay.textContent = steps[stepIdx].label;
                slider.value = stepIdx;
            }}
            updateUI(0);

            slider.oninput = () => {{
                const idx = parseInt(slider.value);
                updateUI(idx);
                Plotly.animate(gd, [steps[idx].label], {{frame: {{duration: 0, redraw: true}}, mode: 'immediate'}});
            }};

            playBtn.onclick = () => {{
                isPlaying = true;
                playBtn.classList.add('active'); pauseBtn.classList.remove('active');
                Plotly.restyle(gd, {{visible: [true, false]}}, [0, 1]); // Low-res
                Plotly.animate(gd, null, {{frame: {{duration: currentDuration, redraw: true}}, fromcurrent: true}});
            }};

            pauseBtn.onclick = () => {{
                isPlaying = false;
                pauseBtn.classList.add('active'); playBtn.classList.remove('active');
                Plotly.animate(gd, [null], {{mode: 'immediate'}});
                Plotly.restyle(gd, {{visible: [false, true]}}, [0, 1]); // High-res
            }};

            gd.on('plotly_animatingframe', (e) => {{
                const idx = steps.findIndex(s => s.label === e.name);
                if (idx !== -1) updateUI(idx);
            }});

            const jumpBtn = document.getElementById('jump-btn');
            const jumpDate = document.getElementById('jump-date');
            
            // Set jump date limits
            jumpDate.min = steps[0].label;
            jumpDate.max = steps[steps.length-1].label;
            jumpDate.value = steps[0].label;

            jumpBtn.onclick = () => {{
                const target = jumpDate.value;
                const idx = steps.findIndex(s => s.label >= target);
                if (idx !== -1) {{
                    updateUI(idx);
                    Plotly.animate(gd, [steps[idx].label], {{frame: {{duration: 0, redraw: true}}, mode: 'immediate'}});
                    if (isPlaying) pauseBtn.click();
                }}
            }};
        }});
        </script>
        """
    elif earthquake_data:
        quakes_json = json.dumps(earthquake_data)
        extra_scripts += f"""
        <div id="settings-bar" class="glass-panel">
            <div class="settings-group">
                <div class="label">Color Mode</div>
                <button class="settings-btn" id="color-toggle">Depth ▾</button>
                <div class="glass-panel glass-menu" id="color-menu">
                    <div class="menu-item active" data-mode="dep">Depth</div>
                    <div class="menu-item" data-mode="date">Date</div>
                    <div class="menu-item" id="cluster-wire-btn" data-mode="cluster_wire" style="display:none;">Cluster (Wireframe)</div>
                    <div class="menu-item" id="cluster-solid-btn" data-mode="cluster_solid" style="display:none;">Cluster (Solid)</div>
                </div>
            </div>

            <div class="settings-group" id="view-mode-group" style="margin-top:12px; display:none;">
                <div class="label">View Type</div>
                <button class="settings-btn" id="view-mode-toggle">Scatter ▾</button>
                <div class="glass-panel glass-menu" id="view-mode-menu">
                    <div class="menu-item active" data-mode="scatter">Scatter Plot</div>
                    <div class="menu-item" data-mode="heatmap">Heatmap</div>
                </div>
            </div>

            <div class="settings-group" style="margin-top:20px">
                <div class="label">Min. Magnitude</div>
                <input type="number" class="glass-input" id="mag-num" min="0.5" max="9" step="0.1" value="0.5">
            </div>

            <div class="settings-group" style="margin-top:12px">
                <div class="label">Max. Depth (km)</div>
                <input type="number" class="glass-input" id="dep-num" min="0" max="100" step="1" value="30">
            </div>

            <button class="settings-btn" id="apply-filters-btn" style="margin-top:20px; justify-content:center; background: rgba(165, 180, 252, 0.2); border-color: rgba(165, 180, 252, 0.4);">
                Apply Filters
            </button>
        </div>

        <div id="filter-loader" class="glass-panel"><div class="spinner" style="width:30px; height:30px"></div></div>

        <div id="filter-bar" class="glass-panel">
            <input type="date" id="filter-start">
            <span style="opacity:0.6">to</span>
            <input type="date" id="filter-end">
        </div>

        <script>
        const quakeData = {quakes_json};
        const clusterColors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52'];
        window.addEventListener('load', function() {{
            const gd = document.querySelector('.plotly-graph-div');
            const startInput = document.getElementById('filter-start');
            const endInput = document.getElementById('filter-end');
            const magInput = document.getElementById('mag-num');
            const depInput = document.getElementById('dep-num');
            
            const colorToggle = document.getElementById('color-toggle');
            const colorMenu = document.getElementById('color-menu');
            const viewModeToggle = document.getElementById('view-mode-toggle');
            const viewModeMenu = document.getElementById('view-mode-menu');
            const viewModeGroup = document.getElementById('view-mode-group');

            const dates = quakeData.times.map(t => t.slice(0, 10));
            const uniqueDates = Array.from(new Set(dates)).sort();

            startInput.min = endInput.min = uniqueDates[0];
            startInput.max = endInput.max = uniqueDates[uniqueDates.length - 1];
            startInput.value = uniqueDates[0];
            endInput.value = uniqueDates[uniqueDates.length - 1];

            magInput.min = Math.min(...quakeData.magnitude);
            magInput.max = Math.max(...quakeData.magnitude);
            magInput.value = magInput.min;

            const absDeps = quakeData.depth.map(Math.abs);
            depInput.max = Math.ceil(Math.max(...absDeps));
            depInput.value = depInput.max;

            let currentColorMode = 'dep';
            let currentViewMode = 'scatter';

            const is3D = (gd.layout.scene !== undefined);
            if (!is3D && gd.data.length > 1) viewModeGroup.style.display = 'block';
            if (is3D && quakeData.cluster) {{
                const cwBtn = document.getElementById('cluster-wire-btn');
                const csBtn = document.getElementById('cluster-solid-btn');
                if (cwBtn) cwBtn.style.display = 'block';
                if (csBtn) csBtn.style.display = 'block';
            }}

            function setupMenu(btn, menu) {{
                btn.onclick = (e) => {{
                    e.stopPropagation();
                    document.querySelectorAll('.glass-menu').forEach(m => {{ if (m !== menu) m.classList.remove('show'); }});
                    menu.classList.toggle('show');
                }};
            }}
            setupMenu(colorToggle, colorMenu);
            if (viewModeToggle) setupMenu(viewModeToggle, viewModeMenu);
            document.onclick = () => document.querySelectorAll('.glass-menu').forEach(m => m.classList.remove('show'));

            colorMenu.querySelectorAll('.menu-item').forEach(item => {{
                item.onclick = () => {{
                    currentColorMode = item.dataset.mode;
                    colorMenu.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    colorToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
                    applyFilterWithLoader();
                }};
            }});

            if (viewModeMenu) {{
                viewModeMenu.querySelectorAll('.menu-item').forEach(item => {{
                    item.onclick = () => {{
                        currentViewMode = item.dataset.mode;
                        viewModeMenu.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
                        item.classList.add('active');
                        viewModeToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
                        applyFilterWithLoader();
                    }};
                }});
            }}

            const applyBtn = document.getElementById('apply-filters-btn');
            const filterLoader = document.getElementById('filter-loader');

            function applyFilterWithLoader() {{
                if (is3D) {{
                    filterLoader.classList.add('show');
                    setTimeout(() => {{
                        try {{
                            applyFilter();
                        }} catch (e) {{
                            console.error('Filter Error:', e);
                        }}
                        filterLoader.classList.remove('show');
                    }}, 50);
                }} else {{
                    try {{
                        applyFilter();
                    }} catch (e) {{
                        console.error('Filter Error:', e);
                    }}
                }}
            }}

            function sanitizeInput(el, defVal) {{
                let val = el.value.trim();
                // Fix leading zeros: 05 -> 5, 0.5 -> 0.5
                if (/^0[1-9]/.test(val)) val = val.replace(/^0+/, '');
                if (!val) val = defVal;
                el.value = val;
                applyFilterWithLoader();
            }}

            magInput.onblur = () => sanitizeInput(magInput, magInput.min);
            depInput.onblur = () => sanitizeInput(depInput, depInput.max);

            if (is3D) {{
                applyBtn.onclick = applyFilterWithLoader;
            }} else {{
                applyBtn.style.display = 'none';
                magInput.oninput = applyFilterWithLoader;
                depInput.oninput = applyFilterWithLoader;
                startInput.onchange = endInput.onchange = applyFilterWithLoader;
                applyFilterWithLoader(); // Initial apply for 2D
            }}

            function applyFilter() {{
                const start = startInput.value, end = endInput.value;
                const minMag = parseFloat(magInput.value) || 0, maxDep = parseFloat(depInput.value) || 999;
                const indices = [];

                for (let i = 0; i < dates.length; i++) {{
                    if (dates[i] >= start && dates[i] <= end && 
                        quakeData.magnitude[i] >= minMag && 
                        Math.abs(quakeData.depth[i]) <= maxDep) indices.push(i);
                }}

                const filtered = {{
                    lon: indices.map(i => quakeData.longitude[i]),
                    lat: indices.map(i => quakeData.latitude[i]),
                    mag: indices.map(i => quakeData.magnitude[i]),
                    dep: indices.map(i => quakeData.depth[i]),
                    times: indices.map(i => quakeData.times[i]),
                    dnum: indices.map(i => quakeData.dates_num[i]),
                    cluster: quakeData.cluster ? indices.map(i => quakeData.cluster[i]) : null,
                    hover: indices.map(i => quakeData.hover[i])
                }};

                const isMag = (currentColorMode === 'mag');
                const isCluster = (currentColorMode === 'cluster');
                const isHeatmap = (currentViewMode === 'heatmap');

                if (is3D) {{
                    const isDep = (currentColorMode === 'dep');
                    const isMag = (currentColorMode === 'mag');
                    const isClusterWire = (currentColorMode === 'cluster_wire');
                    const isClusterSolid = (currentColorMode === 'cluster_solid');
                    const isClusterAny = isClusterWire || isClusterSolid;
                    
                    const traceIdx = (isMag || isDep || isClusterAny) ? 6 : 7;
                    let limits;
                    if (isDep) limits = quakeData.dep_limit;
                    else if (isMag) limits = quakeData.mag_limit;
                    else limits = quakeData.date_limit;

                    let colorArr;
                    if (isDep) colorArr = filtered.dep;
                    else if (isMag) colorArr = filtered.mag;
                    else colorArr = filtered.dnum;

                    let colorScale = (isMag || isDep) ? 'Plasma' : 'Turbo';
                    let showScale = true;

                    if (isClusterAny) {{
                        colorArr = filtered.cluster.map(c => clusterColors[c % clusterColors.length]);
                        colorScale = null;
                        showScale = false;
                        limits = [0, 1];
                    }}

                    Plotly.restyle(gd, {{ visible: false }}, [6, 7]);
                    const restyleUpdate = {{
                        x: [filtered.lon], y: [filtered.lat], z: [filtered.dep],
                        'marker.size': [filtered.mag],
                        'marker.color': [colorArr],
                        'marker.cmin': [limits[0]],
                        'marker.cmax': [limits[1]],
                        hovertext: [filtered.hover], visible: true
                    }};
                    
                    if (isClusterAny) {{
                        restyleUpdate['marker.colorscale'] = null;
                        restyleUpdate['marker.showscale'] = false;
                        restyleUpdate['marker.colorbar.visible'] = false;
                    }} else {{
                        restyleUpdate['marker.colorscale'] = colorScale;
                        restyleUpdate['marker.showscale'] = true;
                        restyleUpdate['marker.colorbar.visible'] = true;
                        restyleUpdate['marker.colorbar.title'] = isDep ? 'Depth' : (isMag ? 'Magnitude' : 'Days');
                    }}
                    
                    Plotly.restyle(gd, restyleUpdate, [traceIdx]);
                    
                    // Toggle the Legend and its Proxy Traces (13-17)
                    Plotly.relayout(gd, {{ showlegend: isClusterAny }});
                    if (quakeData.cluster) {{
                        const indices_proxies = [13, 14, 15, 16, 17];
                        Plotly.restyle(gd, {{ visible: isClusterAny }}, indices_proxies);
                    }}

                    // Handle Cluster Wireframes (Indices 1-5) and Solid Volumes (Indices 8-12)
                    if (quakeData.cluster) {{
                        const maxCluster = Math.max(...quakeData.cluster);
                        for (let c = 0; c <= maxCluster; c++) {{
                            // Toggle Wireframes (1-5)
                            if (gd.data.length > 1 + c) {{
                                Plotly.restyle(gd, {{ 
                                    visible: isClusterWire,
                                    hoverinfo: 'skip'
                                }}, [1 + c]);
                            }}
                            // Toggle Solid Volumes (8-12)
                            if (gd.data.length > 8 + c) {{
                                Plotly.restyle(gd, {{ 
                                    visible: isClusterSolid,
                                    hoverinfo: 'skip',
                                    hovertemplate: null
                                }}, [8 + c]);
                            }}
                        }}
                    }}

                }} else {{
                    if (isHeatmap) {{
                        Plotly.restyle(gd, {{ visible: false }}, [0]);
                        Plotly.restyle(gd, {{ lat: [filtered.lat], lon: [filtered.lon], z: [filtered.mag], visible: true, hovertext: [filtered.hover] }}, [1]);
                    }} else {{
                        Plotly.restyle(gd, {{ visible: false }}, [1]);
                        const limits = isMag ? quakeData.mag_limit : quakeData.date_limit;
                        Plotly.restyle(gd, {{
                            lat: [filtered.lat], lon: [filtered.lon],
                            'marker.size': [filtered.mag],
                            'marker.color': [isMag ? filtered.mag : filtered.dnum],
                            'marker.cmin': [limits[0]],
                            'marker.cmax': [limits[1]],
                            'marker.colorscale': isMag ? 'Plasma' : 'Turbo',
                            'marker.colorbar.title': isMag ? 'Magnitude' : 'Days',
                            hovertext: [filtered.hover], visible: true
                        }}, [0]);
                    }}
                }}
            }}
        }});
        </script>
        """

    if extra_scripts:
        html_content = html_content.replace('</body>', extra_scripts + '</body>')

    return html_content
