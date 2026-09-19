// --- Debug Logger (set window.__SV_DEBUG = true in DevTools to enable verbose logging) ---
window._svLog = function(...args) { if (window.__SV_DEBUG) console.log('[SV]', ...args); };
window._svWarn = function(...args) { if (window.__SV_DEBUG) console.warn('[SV]', ...args); };
window._svErr = function(...args) { console.error('[SV]', ...args); };  // Errors always logged

// --- Shared Seismic Data Binary Loader ---
window.fetchAndUnpackSeismicData = async function(dataUrl) {
    const [respJson, respBin] = await Promise.all([
        fetch(dataUrl),
        fetch(dataUrl + '/bin')
    ]);
    if (!respJson.ok || !respBin.ok) throw new Error("Data fetch failed");
    const quakeData = await respJson.json();
    const buffer = await respBin.arrayBuffer();

    // Zero-copy Float32Array subarrays
    const f32 = new Float32Array(buffer);
    const count = Math.round(f32[0]);
    const clusterCount = Math.round(f32[1]);

    quakeData.longitude = f32.subarray(2, 2 + count);
    quakeData.latitude  = f32.subarray(2 + count, 2 + 2 * count);
    quakeData.magnitude = f32.subarray(2 + 2 * count, 2 + 3 * count);
    quakeData.depth     = f32.subarray(2 + 3 * count, 2 + 4 * count);
    quakeData.dates_num = f32.subarray(2 + 4 * count, 2 + 5 * count);
    if (clusterCount > 0) {
        quakeData.cluster = f32.subarray(2 + 5 * count, 2 + 5 * count + clusterCount);
    }
    return quakeData;
};

// --- Shared Cluster Palette & Color Generator ---
window.CLUSTER_PALETTE = [
    '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52',
    '#00b8d4', '#ff1744', '#00e676', '#d500f9', '#ff9100', '#2979ff', '#ff5252', '#00e5ff', '#76ff03', '#f50057',
    '#3d5afe', '#ffea00', '#64ffda', '#ff3d00', '#1de9b6', '#c6ff00', '#ff6d00', '#00b0ff', '#f4ff81', '#ff5722'
];

window.getClusterColor = function(lbl) {
    if (lbl < 0) return '#888888';
    if (lbl < window.CLUSTER_PALETTE.length) return window.CLUSTER_PALETTE[lbl];
    const h = (lbl * 137.508) % 360;
    const s = 0.8;
    const l = 0.55;
    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs((h / 60) % 2 - 1));
    const m = l - c / 2;
    let r = 0, g = 0, b = 0;
    if (h < 60) { r = c; g = x; }
    else if (h < 120) { r = x; g = c; }
    else if (h < 180) { g = c; b = x; }
    else if (h < 240) { g = x; b = c; }
    else if (h < 300) { r = x; b = c; }
    else { r = c; b = x; }
    const toHex = (n) => {
        const hx = Math.round((n + m) * 255).toString(16);
        return hx.length === 1 ? '0' + hx : hx;
    };
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
};

// --- Message Synchronization & WebSocket (Delegated to /assets/viz_socket.js) ---
    const updateProgress = window.updateProgress || function() {};

    function getBridgeApi() {
        if (window.pywebview && window.pywebview.api) return window.pywebview.api;
        if (window.parent && window.parent.pywebview && window.parent.pywebview.api) return window.parent.pywebview.api;
        return null;
    }
    window.getBridgeApi = getBridgeApi;

    async function transitionToHub() {
        showInitLoader('Returning to Hub...');
        try {
            const gd = document.querySelector('.plotly-graph-div') || document.getElementById('plot') || document.getElementById('plotly-div');
            if (gd && window.Plotly) window.Plotly.purge(gd);
        } catch(e) {}
        const api = getBridgeApi();
        if (api && api.clear_history) {
            try { await api.clear_history(); } catch(e) {}
        }
        if (window.parent && window.parent.SeismicApp && typeof window.parent.SeismicApp.showHub === 'function') {
            window.parent.SeismicApp.showHub();
        } else {
            setTimeout(() => {
                window.location.href = '/assets/index.html';
            }, 250);
        }
    }

    function purgeCurrentPlot() {
        try {
            const gd = document.querySelector('.plotly-graph-div') || document.getElementById('plot') || document.getElementById('plotly-div');
            if (gd && window.Plotly) window.Plotly.purge(gd);
        } catch(e) {}
    }
    window.purgeCurrentPlot = purgeCurrentPlot;
    window.addEventListener('pagehide', purgeCurrentPlot);
    window.addEventListener('beforeunload', purgeCurrentPlot);

    // --- History Navigation ---
    async function historyGoBack() {
        const api = getBridgeApi();
        if (!api) return;
        showInitLoader('Loading previous view...');
        purgeCurrentPlot();
        if (typeof window.updateHistoryState === 'function') await window.updateHistoryState();
        await api.go_back();
    }

    async function historyGoForward() {
        const api = getBridgeApi();
        if (!api) return;
        showInitLoader('Loading next view...');
        purgeCurrentPlot();
        if (typeof window.updateHistoryState === 'function') await window.updateHistoryState();
        await api.go_forward();
    }

    async function checkHistoryStatus() {
        const controls = document.getElementById('history-controls');
        const backBtn = document.getElementById('history-back-btn');
        const fwdBtn = document.getElementById('history-forward-btn');
        if (!controls || !backBtn || !fwdBtn) return;

        const isClusterView = Boolean(window.IS_CLUSTER_VIEW || (window.SEISMIC_CONFIG && window.SEISMIC_CONFIG.isCluster));

        if (isClusterView) {
            controls.style.display = 'flex';
        }

        const api = getBridgeApi();
        if (!api) {
            if (isClusterView) {
                backBtn.disabled = true;
                fwdBtn.disabled = true;
                backBtn.style.opacity = '0.35';
                backBtn.style.cursor = 'not-allowed';
                fwdBtn.style.opacity = '0.35';
                fwdBtn.style.cursor = 'not-allowed';
            }
            return;
        }
        try {
            const status = await api.get_history_status();
            const canBack = Boolean(status && status.can_go_back);
            const canFwd = Boolean(status && status.can_go_forward);

            if (isClusterView || canBack || canFwd) {
                controls.style.display = 'flex';
                backBtn.disabled = !canBack;
                fwdBtn.disabled = !canFwd;
                backBtn.style.opacity = canBack ? '1' : '0.35';
                backBtn.style.cursor = canBack ? 'pointer' : 'not-allowed';
                fwdBtn.style.opacity = canFwd ? '1' : '0.35';
                fwdBtn.style.cursor = canFwd ? 'pointer' : 'not-allowed';
            } else {
                controls.style.display = 'none';
            }
        } catch (e) {
            console.error('Failed to get history status:', e);
        }
    }
    window.checkHistoryStatus = checkHistoryStatus;

    let initLoaderTimeout = null;

    function hideInitLoader() {
        const executeReveal = () => {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    const il = document.getElementById('init-loader');
                    if (il) {
                        if (initLoaderTimeout) clearTimeout(initLoaderTimeout);
                        il.style.opacity = '0';
                        initLoaderTimeout = setTimeout(() => { 
                            il.style.display = 'none';
                            const infoBtn = document.getElementById('info-btn');
                            if (infoBtn) infoBtn.classList.add('visible');
                            const overlayBtn = document.getElementById('overlay-btn');
                            if (overlayBtn) overlayBtn.classList.add('visible');
                            const screenshotBtn = document.getElementById('screenshot-btn');
                            if (screenshotBtn) screenshotBtn.classList.add('visible');
                        }, 400);
                    }
                    if (window.parent && window.parent.SeismicApp) {
                        if (typeof window.parent.SeismicApp.revealVisualization === 'function') {
                            window.parent.SeismicApp.revealVisualization();
                        } else if (typeof window.parent.SeismicApp.hideOverlay === 'function') {
                            window.parent.SeismicApp.hideOverlay();
                        }
                    }
                });
            });
        };

        const gd = document.querySelector('.plotly-graph-div') || document.getElementById('plot') || document.getElementById('plotly-div');
        if (gd && gd._fullLayout) {
            setTimeout(executeReveal, 80);
        } else {
            setTimeout(executeReveal, 140);
        }
    }

    function showInitLoader(msg) {
        if (window.parent && window.parent.SeismicApp && typeof window.parent.SeismicApp.showOverlay === 'function') {
            window.parent.SeismicApp.showOverlay(msg || 'Loading visualization...');
            return;
        }
        const il = document.getElementById('init-loader');
        if (il) {
            if (initLoaderTimeout) clearTimeout(initLoaderTimeout);
            const textEl = il.querySelector('.loader-text');
            if (textEl && msg) textEl.textContent = msg;
            il.style.display = 'flex';
            il.style.opacity = '0';
            il.style.transition = 'opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1)';
            setTimeout(() => { il.style.opacity = '1'; }, 10);
        }
    }



    const SeismicUI = {
        _activeTomographyData: null,
        _activeUpliftData: null,
        _layerScales: {
            earthquakes: 'Viridis',
            vectors: 'Vectors',
            tomo: 'Tomography',
            uplift: 'Uplift'
        },

        getAvailableLegendScales() {
            const gd = document.querySelector('.plotly-graph-div') || 
                       (window.plotlyId ? document.getElementById(window.plotlyId) : null) || 
                       document.getElementById('plotly-div') || 
                       document.getElementById('plot');

            let isClustering = false;
            const clusterList = document.getElementById('cluster-list');
            if (typeof window.animClusteringEnabled !== 'undefined' && window.animClusteringEnabled) {
                isClustering = true;
            } else if (clusterList && clusterList.children && clusterList.children.length > 0 && clusterList.style.display !== 'none') {
                isClustering = true;
            } else if (window.quakeData && (window.quakeData.n_clusters > 0 || (window.quakeData.cluster && window.quakeData.cluster.length > 0))) {
                isClustering = true;
            } else if (typeof window.lockedClusters !== 'undefined') {
                isClustering = true;
            }

            const available = [];
            if (isClustering) {
                available.push('clusters');
            } else {
                available.push('earthquakes');
            }

            // Vector detection: check internal flag, global UI flag, DOM checkbox or actual Plotly traces
            const evCheck = document.getElementById('event-vectors-check');
            const hasVectorsChecked = Boolean(evCheck && evCheck.checked);
            const hasVectorsInPlot = Boolean(gd && gd.data && gd.data.some(tr => tr && tr.visible !== false && (
                tr.name === 'Consecutive Event Vectors' || 
                tr.name === 'Event Arrowheads' || 
                (typeof tr.name === 'string' && (tr.name.includes('Vector') || tr.name.includes('Arrow')))
            )));
            const vectorsActive = Boolean(
                this._activeConsecutiveArrows || 
                (window.SeismicUI && window.SeismicUI._activeConsecutiveArrows) || 
                hasVectorsChecked || 
                hasVectorsInPlot
            );

            if (vectorsActive) {
                available.push('vectors');
                this._activeConsecutiveArrows = true;
                if (window.SeismicUI) window.SeismicUI._activeConsecutiveArrows = true;
            }

            // Tomography detection
            const hasTomoInPlot = Boolean(gd && gd.data && gd.data.some(tr => tr && tr.visible !== false && typeof tr.name === 'string' && (
                tr.name.toLowerCase().includes('tomography') || 
                tr.name.includes('Vp/Vs') || 
                tr.name.includes('Tomografia')
            )));
            if (this._activeTomographyData || hasTomoInPlot) {
                available.push('tomo');
            }

            // Uplift detection
            const hasUpliftInPlot = Boolean(gd && gd.data && gd.data.some(tr => tr && tr.visible !== false && typeof tr.name === 'string' && (
                tr.name.includes('Uplift') || 
                tr.name.includes('GNSS') || 
                tr.name.includes('Deformazione')
            )));
            if (this._activeUpliftData || hasUpliftInPlot) {
                available.push('uplift');
            }

            return available;
        },

        updateLegendSwapButtonVisibility() {
            const btn = document.getElementById('btn-swap-legend');
            if (!btn) return;

            const available = this.getAvailableLegendScales();
            const legend = document.getElementById('glass-legend');
            const clusterList = document.getElementById('cluster-list');

            if (available.length <= 1) {
                btn.style.display = 'none';
                if (legend && clusterList && clusterList.style.display !== 'none') {
                    legend.style.paddingBottom = '0.85rem';
                }
                if (window._currentLegendMode === 'vectors') {
                    window._currentLegendMode = available[0];
                }
            } else {
                btn.style.display = 'flex';
                if (legend) {
                    legend.style.display = 'flex';
                    if (clusterList && clusterList.style.display !== 'none') {
                        legend.style.paddingBottom = '2.6rem';
                    }
                }
                if (!window._currentLegendMode || !available.includes(window._currentLegendMode)) {
                    window._currentLegendMode = available[0];
                }

                const currentIdx = available.indexOf(window._currentLegendMode);
                const nextMode = available[(currentIdx + 1) % available.length];
                const modeLabels = {
                    'clusters': 'Clusters',
                    'earthquakes': 'Quakes',
                    'vectors': 'Vectors',
                    'tomo': 'Tomo',
                    'uplift': 'Uplift'
                };
                btn.innerHTML = `⇄ Scale: ${modeLabels[nextMode] || nextMode}`;
                btn.title = `Switch color scale to ${modeLabels[nextMode] || nextMode}`;
            }
        },

        initLegendScaleMenu() {
            const btn = document.getElementById('legend-scale-toggle');
            const menu = document.getElementById('legend-scale-menu');
            if (!btn || !menu) return;

            // Move menu to document.body so it isn't trapped or clipped by #glass-legend's overflow:hidden or containing block
            if (menu.parentElement !== document.body) {
                document.body.appendChild(menu);
            }

            btn.onclick = (e) => {
                e.stopPropagation();
                const wasShowing = menu.classList.contains('show');
                document.querySelectorAll('.glass-menu').forEach(m => m.classList.remove('show'));
                if (this.closeBottomLeftPopups) this.closeBottomLeftPopups();

                if (!wasShowing) {
                    const rect = btn.getBoundingClientRect();
                    const legend = document.getElementById('glass-legend');
                    const legendRect = legend ? legend.getBoundingClientRect() : rect;
                    menu.style.position = 'fixed';
                    menu.style.zIndex = '9999999';
                    const menuHeight = 280;
                    const topPos = Math.max(10, Math.min(window.innerHeight - menuHeight - 10, rect.top - 40));
                    menu.style.top = topPos + 'px';
                    let rightDist = (window.innerWidth - legendRect.left) + 8;
                    if (rightDist + 120 > window.innerWidth - 8) {
                        rightDist = Math.max(10, window.innerWidth - 120 - 8);
                    }
                    menu.style.right = rightDist + 'px';
                    menu.style.left = 'auto';
                    menu.classList.add('show');
                }
            };

            menu.querySelectorAll('.menu-item').forEach(item => {
                item.onclick = (e) => {
                    e.stopPropagation();
                    menu.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    const scaleName = item.dataset.val;
                    btn.title = 'Color scale: ' + scaleName;
                    const swatch = document.getElementById('legend-scale-swatch');
                    if (swatch) {
                        const sColors = (window.COLORS_MAP && window.COLORS_MAP[scaleName]) ? window.COLORS_MAP[scaleName] : ['#440154', '#fde725'];
                        swatch.style.background = `linear-gradient(to top, ${sColors.join(',')})`;
                    }
                    menu.classList.remove('show');
                    this.changeActiveLegendScale(scaleName);
                };
            });
        },

        changeActiveLegendScale(scaleName) {
            let isClustering = false;
            if (typeof window.animClusteringEnabled !== 'undefined' && window.animClusteringEnabled) {
                isClustering = true;
            } else if (typeof window.lockedClusters !== 'undefined') {
                isClustering = true;
            }
            const currentMode = window._currentLegendMode || (isClustering ? 'clusters' : 'earthquakes');
            if (currentMode === 'clusters') return;

            if (!this._layerScales) {
                this._layerScales = {
                    earthquakes: 'Viridis',
                    vectors: 'Vectors',
                    tomo: 'Tomography',
                    uplift: 'Uplift'
                };
            }
            this._layerScales[currentMode] = scaleName;
            if (window.SeismicUI) window.SeismicUI._layerScales = this._layerScales;
            if (window.SeismicLayers) window.SeismicLayers._layerScales = this._layerScales;

            const btn = document.getElementById('legend-scale-toggle');
            if (btn) {
                btn.title = 'Color scale: ' + scaleName;
                const swatch = document.getElementById('legend-scale-swatch');
                if (swatch) {
                    const sColors = (window.COLORS_MAP && window.COLORS_MAP[scaleName]) ? window.COLORS_MAP[scaleName] : (typeof COLORS_MAP !== 'undefined' && COLORS_MAP[scaleName] ? COLORS_MAP[scaleName] : ['#440154', '#fde725']);
                    swatch.style.background = `linear-gradient(to top, ${sColors.join(',')})`;
                }
            }

            let loader = document.getElementById('filter-loader');
            if (!loader) {
                loader = document.createElement('div');
                loader.id = 'filter-loader';
                loader.innerHTML = '<p class="loader-text">Applying Filters...</p><div class="overlay-progress-bar"><div class="overlay-progress-fill overlay-progress-track"></div></div>';
                document.body.appendChild(loader);
            }
            loader.classList.add('show');

            setTimeout(() => {
                try {
                    const gd = document.querySelector('.plotly-graph-div') || (window.plotlyId ? document.getElementById(window.plotlyId) : null) || document.getElementById('plotly-div') || document.getElementById('plot');
                    const pScale = (typeof window.getPlotlyScale === 'function') ? window.getPlotlyScale(scaleName) : (typeof getPlotlyScale === 'function' ? getPlotlyScale(scaleName) : 'Viridis');
                    const inv = (this._layerInverts && this._layerInverts[currentMode]) || false;

                    if (currentMode === 'earthquakes') {
                        if (window._earthquakeLegendState) {
                            window._earthquakeLegendState.scaleName = scaleName;
                        }
                        if (typeof window.setEarthquakeScale === 'function') {
                            window.setEarthquakeScale(scaleName);
                        }
                        if (gd && gd.data) {
                            let updatedAny = false;
                            for (let i = 0; i < gd.data.length; i++) {
                                const tr = gd.data[i];
                                if (!tr) continue;
                                const name = tr.name || '';
                                if (tr.type === 'scatter3d' && (
                                    name.includes('Earthquakes') || name.includes('Color:') || name === 'Depth' || name === 'Date' || name === 'Magnitude' ||
                                    (!name.includes('Vectors') && !name.includes('Arrow') && !name.includes('Station') && !name.includes('Uplift') && !name.includes('Tomography') && !name.includes('Structural') && !name.includes('Terrain') && !name.includes('Mesh'))
                                )) {
                                    if (!tr.marker) tr.marker = {};
                                    tr.marker.colorscale = pScale;
                                    tr.marker.reversescale = inv;
                                    try {
                                        Plotly.restyle(gd, {
                                            'marker.colorscale': [pScale],
                                            'marker.reversescale': [inv]
                                        }, [i]);
                                    } catch (e) {}
                                    updatedAny = true;
                                } else if ((tr.type === 'scattermapbox' || tr.type === 'scattermap') && (name.includes('Earthquakes') || (!name.includes('Station') && !name.includes('Uplift') && !name.includes('Tomography')))) {
                                    if (!tr.marker) tr.marker = {};
                                    tr.marker.colorscale = pScale;
                                    tr.marker.reversescale = inv;
                                    try {
                                        Plotly.restyle(gd, {
                                            'marker.colorscale': [pScale],
                                            'marker.reversescale': [inv]
                                        }, [i]);
                                    } catch (e) {}
                                    updatedAny = true;
                                } else if ((tr.type === 'densitymapbox' || tr.type === 'densitymap') && (name.includes('Heatmap') || name.includes('Earthquakes'))) {
                                    tr.colorscale = pScale;
                                    tr.reversescale = inv;
                                    try {
                                        Plotly.restyle(gd, {
                                            'colorscale': [pScale],
                                            'reversescale': [inv]
                                        }, [i]);
                                    } catch (e) {}
                                    updatedAny = true;
                                }
                            }
                            if (updatedAny) {
                                try { Plotly.redraw(gd); } catch (e) { try { Plotly.react(gd, gd.data, gd.layout); } catch (e2) {} }
                            }
                        }
                        if (window._earthquakeLegendState) {
                            const s = window._earthquakeLegendState;
                            updateGlassLegendInternal(s.show, s.title, scaleName, s.invert, s.limits, s.dateInfo);
                        }
                    } else if (currentMode === 'vectors') {
                        if (gd && gd.data) {
                            for (let i = 0; i < gd.data.length; i++) {
                                const tr = gd.data[i];
                                if (!tr) continue;
                                if (tr.name === 'Consecutive Event Vectors') {
                                    if (!tr.line) tr.line = {};
                                    tr.line.colorscale = pScale;
                                    tr.line.reversescale = inv;
                                    try { Plotly.restyle(gd, { 'line.colorscale': [pScale], 'line.reversescale': [inv] }, [i]); } catch (e) {}
                                } else if (tr.name === 'Event Arrowheads') {
                                    tr.colorscale = pScale;
                                    tr.reversescale = inv;
                                    try { Plotly.restyle(gd, { 'colorscale': [pScale], 'reversescale': [inv] }, [i]); } catch (e) {}
                                }
                            }
                            try { Plotly.redraw(gd); } catch (e) { try { Plotly.react(gd, gd.data, gd.layout); } catch (e2) {} }
                        }
                        const maxV = this._consecutiveVectorCount || 100;
                        updateGlassLegendInternal(true, 'VECTOR N°', scaleName, inv, [1, maxV], null);
                    } else if (currentMode === 'tomo') {
                        if (gd && gd.data) {
                            for (let i = 0; i < gd.data.length; i++) {
                                const tr = gd.data[i];
                                if (!tr) continue;
                                const name = tr.name || '';
                                if (tr.type === 'surface' || name.includes('Terrain') || name.includes('Map')) continue;
                                const isTomo = name.toLowerCase().includes('tomography') || name.includes('Vp/Vs') || name.includes('Tomografia') || tr.type === 'volume';
                                if (isTomo) {
                                    tr.colorscale = pScale;
                                    tr.reversescale = inv;
                                    try { Plotly.restyle(gd, { 'colorscale': [pScale], 'reversescale': [inv] }, [i]); } catch (e) {}
                                }
                            }
                            try { Plotly.redraw(gd); } catch (e) { try { Plotly.react(gd, gd.data, gd.layout); } catch (e2) {} }
                        }
                        updateGlassLegendInternal(true, 'Tomo Vp/Vs', scaleName, inv, [1.15, 2.35], null);
                    } else if (currentMode === 'uplift') {
                        let minVal = 0, maxVal = 80;
                        if (this._activeUpliftData) {
                            const u = this._activeUpliftData;
                            const vals = u.up_m || (u.interp_grid ? u.interp_grid.up_m : []) || [];
                            let minU = 9999, maxU = -9999;
                            for (let i = 0; i < vals.length; i++) {
                                if (vals[i] < minU) minU = vals[i];
                                if (vals[i] > maxU) maxU = vals[i];
                            }
                            if (minU !== 9999) { minVal = minU * 1000; maxVal = maxU * 1000; }
                        }
                        if (gd && gd.data) {
                            for (let i = 0; i < gd.data.length; i++) {
                                const tr = gd.data[i];
                                if (!tr) continue;
                                const name = tr.name || '';
                                if (name.includes('Uplift') && (tr.type === 'surface' || tr.type === 'densitymapbox' || tr.type === 'densitymap' || tr.type === 'choroplethmapbox' || tr.type === 'choroplethmap')) {
                                    tr.colorscale = pScale;
                                    tr.reversescale = inv;
                                    try { Plotly.restyle(gd, { 'colorscale': [pScale], 'reversescale': [inv] }, [i]); } catch (e) {}
                                }
                            }
                            try { Plotly.redraw(gd); } catch (e) { try { Plotly.react(gd, gd.data, gd.layout); } catch (e2) {} }
                        }
                        updateGlassLegendInternal(true, 'Uplift (mm)', scaleName, inv, [minVal, maxVal], null);
                    }
                } catch (err) {
                    console.error('Error applying scale change:', err);
                } finally {
                    setTimeout(() => {
                        if (loader) loader.classList.remove('show');
                    }, 120);
                }
            }, 30);
        },

        toggleInvertScale() {
            const invertCheck = document.getElementById('invert-scale');
            if (!invertCheck) return;
            const inv = invertCheck.checked;

            let isClustering = false;
            if (typeof window.animClusteringEnabled !== 'undefined' && window.animClusteringEnabled) {
                isClustering = true;
            } else if (typeof window.lockedClusters !== 'undefined') {
                isClustering = true;
            }
            const currentMode = window._currentLegendMode || (isClustering ? 'clusters' : 'earthquakes');
            if (currentMode === 'clusters') return;

            if (!this._layerInverts) {
                this._layerInverts = {
                    earthquakes: false,
                    vectors: false,
                    tomo: false,
                    uplift: false
                };
            }
            this._layerInverts[currentMode] = inv;

            let loader = document.getElementById('filter-loader');
            if (!loader) {
                loader = document.createElement('div');
                loader.id = 'filter-loader';
                loader.innerHTML = '<p class="loader-text">Applying Filters...</p><div class="overlay-progress-bar"><div class="overlay-progress-fill overlay-progress-track"></div></div>';
                document.body.appendChild(loader);
            }
            loader.classList.add('show');

            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    setTimeout(() => {
                        try {
                            const gd = document.querySelector('.plotly-graph-div') || (window.plotlyId ? document.getElementById(window.plotlyId) : null) || document.getElementById('plotly-div') || document.getElementById('plot');
                            if (currentMode === 'earthquakes') {
                                if (typeof window.setEarthquakeInvert === 'function') {
                                    window.setEarthquakeInvert(inv);
                                } else if (typeof window.applyColorRestyleOnly === 'function') {
                                    window.applyColorRestyleOnly();
                                } else if (typeof window.applyFilterWithLoader === 'function') {
                                    window.applyFilterWithLoader();
                                } else if (typeof window.updateView === 'function') {
                                    window.updateView();
                                } else if (window._earthquakeLegendState) {
                                    const s = window._earthquakeLegendState;
                                    s.invert = inv;
                                    updateGlassLegendInternal(s.show, s.title, s.scaleName, inv, s.limits, s.dateInfo);
                                    if (gd && gd.data) {
                                        for (let i = 0; i < gd.data.length; i++) {
                                            const tr = gd.data[i];
                                            if (!tr) continue;
                                            const name = tr.name || '';
                                            if (tr.type === 'scatter3d' && (name === 'Depth' || name === 'Date' || name === 'Magnitude' || name === 'Earthquakes' || (!name.includes('Vectors') && !name.includes('Arrow') && !name.includes('Station') && !name.includes('Uplift') && !name.includes('Tomography')))) {
                                                if (tr.marker) tr.marker.reversescale = inv;
                                            } else if ((tr.type === 'scattermapbox' || tr.type === 'scattermap') && (name.includes('Earthquakes') || (!name.includes('Station') && !name.includes('Uplift') && !name.includes('Tomography')))) {
                                                if (tr.marker) tr.marker.reversescale = inv;
                                            }
                                        }
                                        try { Plotly.react(gd, gd.data, gd.layout); } catch (e) { try { Plotly.redraw(gd); } catch (e2) {} }
                                    }
                                }
                            } else if (currentMode === 'vectors') {
                                if (gd && gd.data) {
                                    for (let i = 0; i < gd.data.length; i++) {
                                        const tr = gd.data[i];
                                        if (!tr) continue;
                                        if (tr.name === 'Consecutive Event Vectors') {
                                            if (tr.line) tr.line.reversescale = inv;
                                        } else if (tr.name === 'Event Arrowheads') {
                                            tr.reversescale = inv;
                                        }
                                    }
                                    try { Plotly.react(gd, gd.data, gd.layout); } catch (e) { try { Plotly.redraw(gd); } catch (e2) {} }
                                }
                                const maxV = this._consecutiveVectorCount || 100;
                                const sc = (this._layerScales && this._layerScales.vectors) ? this._layerScales.vectors : 'Vectors';
                                updateGlassLegendInternal(true, 'VECTOR N°', sc, inv, [1, maxV], null);
                            } else if (currentMode === 'tomo') {
                                if (gd && gd.data) {
                                    for (let i = 0; i < gd.data.length; i++) {
                                        const tr = gd.data[i];
                                        if (!tr) continue;
                                        const name = tr.name || '';
                                        if (tr.type === 'surface' || name.includes('Terrain') || name.includes('Map')) continue;
                                        const isTomo = name.toLowerCase().includes('tomography') || name.includes('Vp/Vs') || name.includes('Tomografia') || tr.type === 'volume';
                                        if (isTomo) {
                                            tr.reversescale = inv;
                                        }
                                    }
                                    try { Plotly.react(gd, gd.data, gd.layout); } catch (e) { try { Plotly.redraw(gd); } catch (e2) {} }
                                }
                                const sc = (this._layerScales && this._layerScales.tomo) ? this._layerScales.tomo : 'Tomography';
                                updateGlassLegendInternal(true, 'Tomo Vp/Vs', sc, inv, [1.15, 2.35], null);
                            } else if (currentMode === 'uplift') {
                                if (gd && gd.data) {
                                    for (let i = 0; i < gd.data.length; i++) {
                                        const tr = gd.data[i];
                                        if (!tr) continue;
                                        const name = tr.name || '';
                                        if (name.includes('Uplift') && (tr.type === 'surface' || tr.type === 'densitymapbox' || tr.type === 'densitymap' || tr.type === 'choroplethmapbox' || tr.type === 'choroplethmap')) {
                                            tr.reversescale = inv;
                                        }
                                    }
                                    try { Plotly.react(gd, gd.data, gd.layout); } catch (e) { try { Plotly.redraw(gd); } catch (e2) {} }
                                }
                                let minVal = 0, maxVal = 80;
                                if (this._activeUpliftData) {
                                    const u = this._activeUpliftData;
                                    const vals = u.up_m || (u.interp_grid ? u.interp_grid.up_m : []) || [];
                                    let minU = 9999, maxU = -9999;
                                    for (let i = 0; i < vals.length; i++) {
                                        if (vals[i] < minU) minU = vals[i];
                                        if (vals[i] > maxU) maxU = vals[i];
                                    }
                                    if (minU !== 9999) { minVal = minU * 1000; maxVal = maxU * 1000; }
                                }
                                const sc = (this._layerScales && this._layerScales.uplift) ? this._layerScales.uplift : 'Uplift';
                                updateGlassLegendInternal(true, 'Uplift (mm)', sc, inv, [minVal, maxVal], null);
                            }
                        } catch (err) {
                            console.error('Error toggling invert scale:', err);
                        } finally {
                            setTimeout(() => {
                                if (loader) loader.classList.remove('show');
                            }, 120);
                        }
                    }, 10);
                });
            });
        },

        initMenu(btn, menu) {
            if (!btn || !menu) return;

            // Move menu to document.body so it isn't trapped or offset by containing blocks
            // formed by backdrop-filter or will-change on ancestors like #left-panel-wrapper
            if (menu.parentElement !== document.body) {
                document.body.appendChild(menu);
            }

            btn.onclick = (e) => {
                e.stopPropagation();
                const wasShowing = menu.classList.contains('show');
                document.querySelectorAll('.glass-menu').forEach(m => m.classList.remove('show'));
                if (this.closeBottomLeftPopups) this.closeBottomLeftPopups();
                
                if (!wasShowing) {
                    const rect = btn.getBoundingClientRect();
                    menu.style.position = 'fixed';
                    menu.style.zIndex = '999999';
                    menu.style.width = 'max-content';
                    menu.style.minWidth = rect.width + 'px';
                    menu.style.left = rect.left + 'px';

                    // Temporarily display invisibly to read actual dimensions
                    menu.style.visibility = 'hidden';
                    menu.classList.add('show');
                    const menuHeight = menu.offsetHeight || 140;
                    const menuWidth = Math.max(rect.width, menu.offsetWidth || 140);
                    menu.classList.remove('show');
                    menu.style.visibility = '';

                    // Position directly underneath the button, or flip above if near bottom edge
                    if (rect.bottom + menuHeight + 12 > window.innerHeight && rect.top > menuHeight + 12) {
                        menu.style.top = (rect.top - menuHeight - 4) + 'px';
                    } else {
                        menu.style.top = (rect.bottom + 4) + 'px';
                    }

                    // Prevent overflowing the right viewport edge
                    if (rect.left + menuWidth > window.innerWidth - 12) {
                        menu.style.left = Math.max(10, window.innerWidth - menuWidth - 12) + 'px';
                    }

                    menu.classList.add('show');
                }
            };
        },
        bindMenu(menu, callback) {
            if (!menu) return;
            menu.querySelectorAll('.menu-item').forEach(item => {
                item.onclick = (e) => {
                    if (e) e.stopPropagation();
                    menu.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    menu.classList.remove('show');
                    if (callback) callback(item);
                };
            });
        },
        setupBoundsValidation(input, defaultValue, onApply) {
            if (!input) return;
            input.onblur = () => {
                let val = input.value.trim();
                // Avoid leading zeros unless it's just '0'
                if (/^0[0-9]/.test(val) && val.length > 1 && val[1] !== '.') val = val.replace(/^0+/, '');
                if (!val) val = defaultValue;
                input.value = val;
                if (onApply) onApply();
            };
        },
        setGroupDisabled(el, disabled) {
            if (!el) return;
            if (disabled) el.classList.add('disabled');
            else el.classList.remove('disabled');
        },
        closeBottomLeftPopups(exceptId = null) {
            if (exceptId !== 'info-panel') {
                const infoPanel = document.getElementById('info-panel');
                if (infoPanel) infoPanel.classList.remove('show');
            }
            if (exceptId !== 'layer-modal') {
                const layerModal = document.getElementById('layer-modal');
                if (layerModal) layerModal.classList.remove('active');
            }
            if (exceptId !== 'export-modal') {
                const exportModal = document.getElementById('export-modal');
                if (exportModal) exportModal.classList.remove('active');
            }
            if (exceptId !== 'shortcuts-modal') {
                const shortcutsModal = document.getElementById('shortcuts-modal');
                if (shortcutsModal) shortcutsModal.classList.remove('active');
            }
            if (exceptId !== 'swarm-chart-dialog') {
                const swarmDialog = document.getElementById('swarm-chart-dialog');
                if (swarmDialog) swarmDialog.classList.remove('active');
            }
            if (exceptId !== 'screenshot-preview-dialog') {
                const ssDialog = document.getElementById('screenshot-preview-dialog');
                if (ssDialog) ssDialog.classList.remove('active');
            }
            if (exceptId !== 'cluster-csv-dialog') {
                const csvDialog = document.getElementById('cluster-csv-dialog');
                if (csvDialog) csvDialog.classList.remove('active');
            }
        },
        toggleInfoPanel(e) {
            if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
            const panel = document.getElementById('info-panel');
            if (!panel) return;

            const isShowing = panel.classList.contains('show');
            
            // Close other menus & popups
            document.querySelectorAll('.glass-menu').forEach(m => m.classList.remove('show'));
            this.closeBottomLeftPopups('info-panel');

            if (!isShowing) {
                // Populate data from global quakeData if available
                const qd = window.quakeData;
                if (qd) {
                    if (qd.graph_bounds) {
                        const gb = qd.graph_bounds; // [min_lat, min_lon, max_lat, max_lon, min_depth]
                        document.getElementById('info-min-lat').textContent = gb[0].toFixed(4) + '°';
                        document.getElementById('info-min-lon').textContent = gb[1].toFixed(4) + '°';
                        document.getElementById('info-max-lat').textContent = gb[2].toFixed(4) + '°';
                        document.getElementById('info-max-lon').textContent = gb[3].toFixed(4) + '°';
                        document.getElementById('info-max-depth').textContent = Math.abs(gb[4]).toFixed(1) + ' km';
                    } else if (qd.bbox) {
                        const b = qd.bbox; // [lat_min, lon_min, lat_max, lon_max]
                        document.getElementById('info-min-lat').textContent = b[0].toFixed(4) + '°';
                        document.getElementById('info-max-lat').textContent = b[2].toFixed(4) + '°';
                        document.getElementById('info-min-lon').textContent = b[1].toFixed(4) + '°';
                        document.getElementById('info-max-lon').textContent = b[3].toFixed(4) + '°';
                        
                        const depths = qd.depth || qd.dep;
                        if (depths && depths.length > 0) {
                            let minVal = depths[0];
                            for (let i = 1; i < depths.length; i++) {
                                if (depths[i] < minVal) minVal = depths[i];
                            }
                            const maxDep = Math.abs(minVal);
                            document.getElementById('info-max-depth').textContent = maxDep.toFixed(1) + ' km';
                        } else {
                            const limits = qd.dep_limit || qd.dep_range;
                            if (limits) {
                                document.getElementById('info-max-depth').textContent = Math.abs(limits[0]).toFixed(1) + ' km';
                            }
                        }
                    }
                }
                panel.classList.add('show');
            } else {
                panel.classList.remove('show');
            }
        },

        _originalMapData: null,
        _overlayActive: false,
        _pendingMapFile: null,
        _pendingStationsPath: null,
        _pendingUpliftPath: null,
        _pendingTomoPath: null,

        isClusteringActive() {
            if (typeof window.IS_CLUSTER_VIEW !== 'undefined' && window.IS_CLUSTER_VIEW) {
                return true;
            }
            if (typeof window.animClusteringEnabled !== 'undefined' && window.animClusteringEnabled && typeof window.animClustersMap !== 'undefined' && window.animClustersMap !== null) {
                return true;
            }
            return false;
        },

        toggleExportModal(e, forceClose = false) {
            if (e === true) {
                forceClose = true;
                e = null;
            }
            if (e && typeof e.stopPropagation === 'function') e.stopPropagation();

            const modal = document.getElementById('export-modal');
            const btn = document.getElementById('btn-export-clusters');
            if (btn) {
                const active = this.isClusteringActive();
                if (active) {
                    btn.disabled = false;
                    btn.style.opacity = '';
                    btn.style.cursor = 'pointer';
                    btn.title = 'Export all identified clusters and outliers';
                } else {
                    btn.disabled = true;
                    btn.style.opacity = '';
                    btn.style.cursor = 'not-allowed';
                    btn.title = 'Available only when clustering is performed (in Cluster View or 4D Animated View with clustering enabled)';
                }
            }

            const swarmBtn = document.getElementById('btn-export-swarm-chart');
            if (swarmBtn) {
                const hasSwarms = (window.quakeData && window.quakeData.swarms && window.quakeData.swarms.length > 0) ||
                                  (window.swarmsList && window.swarmsList.length > 0) ||
                                  (typeof window.isSwarmMode !== 'undefined' && window.isSwarmMode) ||
                                  (window.quakeData && window.quakeData.anim_mode === 'swarm');
                if (hasSwarms) {
                    swarmBtn.style.display = 'block';
                    swarmBtn.title = 'Export Magnitude vs. Time chart of seismic swarms as a PNG image';
                } else {
                    swarmBtn.style.display = 'none';
                }
            }

            if (modal) {
                if (forceClose === true) {
                    modal.classList.remove('active');
                } else {
                    const isShowing = modal.classList.contains('active');
                    document.querySelectorAll('.glass-menu').forEach(m => m.classList.remove('show'));
                    this.closeBottomLeftPopups('export-modal');

                    if (!isShowing) {
                        modal.classList.add('active');
                    } else {
                        modal.classList.remove('active');
                    }
                }
            }
        },

        toggleShortcutsModal(e, forceClose = null) {
            if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
            const modal = document.getElementById('shortcuts-modal');
            if (!modal) return;
            if (forceClose === true) {
                modal.classList.remove('active');
            } else {
                const isShowing = modal.classList.contains('active');
                document.querySelectorAll('.glass-menu').forEach(m => m.classList.remove('show'));
                this.closeBottomLeftPopups('shortcuts-modal');
                if (!isShowing) {
                    modal.classList.add('active');
                } else {
                    modal.classList.remove('active');
                }
            }
        },

        _activeConsecutiveArrows: false,
        _consecutiveVectorCount: 0,

        toggleConsecutiveArrows(forceState = null) {
            if (!window.IS_3D_VIEW || (typeof is3D !== 'undefined' && !is3D)) {
                showStatusToast("Event vectors are only available in 3D views.", false);
                return;
            }
            const chk = document.getElementById('event-vectors-check');
            const btn = document.getElementById('btn-consecutive-arrows');
            const gd = document.querySelector('.plotly-graph-div');
            if (!gd || !gd.data) return;

            const isCurrentlyActive = this._activeConsecutiveArrows;
            const targetState = (forceState !== null) ? forceState : !isCurrentlyActive;

            this.removeConsecutiveArrowTraces(gd);

            if (targetState) {
                let xs = [], ys = [], zs = [];
                
                const cfd = window.currentFilteredData || (window.quakeData && window.quakeData.filtered ? window.quakeData.filtered : null);
                if (cfd && cfd.longitude && cfd.longitude.length > 0) {
                    xs = cfd.longitude;
                    ys = cfd.latitude;
                    zs = cfd.depth;
                } else {
                    const qd = window.quakeData || (window.fullData ? window.fullData : null);
                    if (qd && qd.longitude && qd.longitude.length > 0) {
                        xs = qd.longitude;
                        ys = qd.latitude;
                        zs = qd.depth;
                    } else {
                        for (let i = 0; i < gd.data.length; i++) {
                            const tr = gd.data[i];
                            if (tr && tr.type === 'scatter3d' && tr.x && tr.x.length > 0) {
                                const name = tr.name || '';
                                if (!name.includes('Terrain') && !name.includes('Stations') && !name.includes('Uplift') && !name.includes('Tomography') && !name.includes('Vector') && !name.includes('Arrow') && !name.includes('Centroid') && !name.includes('Hull') && !name.includes('Mesh') && !name.includes('Plane') && !name.includes('Other')) {
                                    for (let k = 0; k < tr.x.length; k++) {
                                        xs.push(tr.x[k]);
                                        ys.push(tr.y[k]);
                                        zs.push(tr.z[k]);
                                    }
                                }
                            }
                        }
                    }
                }

                if (xs.length < 2) {
                    showStatusToast("Not enough 3D points for event vectors.", false);
                    if (chk) chk.checked = false;
                    if (btn) btn.classList.remove('active');
                    this._activeConsecutiveArrows = false;
                    this.updateSwapLegendVisibility();
                    return;
                }

                const lineX = [], lineY = [], lineZ = [], lineColor = [];
                const meshX = [], meshY = [], meshZ = [];
                const meshI = [], meshJ = [], meshK = [];
                const meshIntensity = [];

                let validPairs = 0;
                const totalPairs = xs.length - 1;

                for (let i = 0; i < totalPairs; i++) {
                    const x1 = parseFloat(xs[i]), y1 = parseFloat(ys[i]), z1 = parseFloat(zs[i]);
                    const x2 = parseFloat(xs[i+1]), y2 = parseFloat(ys[i+1]), z2 = parseFloat(zs[i+1]);

                    if (isNaN(x1) || isNaN(y1) || isNaN(z1) || isNaN(x2) || isNaN(y2) || isNaN(z2)) continue;

                    validPairs++;
                    const vectorNum = validPairs; // 1-indexed vector sequence number

                    // 1. Metric coordinate calculations for direction & solid arrowhead
                    const midLat = (y1 + y2) * 0.5;
                    const kmPerDegLon = 111.0 * Math.cos(midLat * Math.PI / 180.0);
                    const kmPerDegLat = 111.0;

                    const dxKm = (x2 - x1) * kmPerDegLon;
                    const dyKm = (y2 - y1) * kmPerDegLat;
                    const dzKm = (z2 - z1);
                    const distKm = Math.sqrt(dxKm * dxKm + dyKm * dyKm + dzKm * dzKm);

                    let stemEndX = x2, stemEndY = y2, stemEndZ = z2;

                    if (distKm > 1e-4) {
                        const ux = dxKm / distKm;
                        const uy = dyKm / distKm;
                        const uz = dzKm / distKm;

                        // Solid cone dimensions for each arrow (slightly larger, sleek and distinct)
                        const headLenKm = Math.min(Math.max(0.010, 0.18 * distKm), 0.060, 0.5 * distKm);
                        const headWidthKm = headLenKm * 0.45;

                        // Perpendicular vector n1
                        let rx = 0, ry = 0, rz = 1;
                        if (Math.abs(uz) > 0.88) { rx = 0; ry = 1; rz = 0; }

                        let n1x = uy * rz - uz * ry;
                        let n1y = uz * rx - ux * rz;
                        let n1z = ux * ry - uy * rx;
                        const n1Len = Math.sqrt(n1x * n1x + n1y * n1y + n1z * n1z) || 1;
                        n1x /= n1Len; n1y /= n1Len; n1z /= n1Len;

                        // Perpendicular vector n2 (u x n1)
                        const n2x = uy * n1z - uz * n1y;
                        const n2y = uz * n1x - ux * n1z;
                        const n2z = ux * n1y - uy * n1x;

                        // Base center point in km
                        const x2Km = x2 * kmPerDegLon;
                        const y2Km = y2 * kmPerDegLat;
                        const z2Km = z2;

                        const baseKmX = x2Km - headLenKm * ux;
                        const baseKmY = y2Km - headLenKm * uy;
                        const baseKmZ = z2Km - headLenKm * uz;

                        const bx = baseKmX / kmPerDegLon;
                        const by = baseKmY / kmPerDegLat;
                        const bz = baseKmZ;

                        stemEndX = (distKm > headLenKm) ? bx : x2;
                        stemEndY = (distKm > headLenKm) ? by : y2;
                        stemEndZ = (distKm > headLenKm) ? bz : z2;

                        // 2. Build Solid 3D Cone Arrowhead Mesh (Figura piena)
                        const K = meshX.length;
                        const N_SIDES = 6;

                        // Vertex 0: Arrow tip
                        meshX.push(x2);
                        meshY.push(y2);
                        meshZ.push(z2);
                        meshIntensity.push(vectorNum);

                        // Vertices 1..N_SIDES: Perimeter around base
                        for (let s = 0; s < N_SIDES; s++) {
                            const angle = (2 * Math.PI * s) / N_SIDES;
                            const cosA = Math.cos(angle);
                            const sinA = Math.sin(angle);
                            const pxKm = baseKmX + headWidthKm * (cosA * n1x + sinA * n2x);
                            const pyKm = baseKmY + headWidthKm * (cosA * n1y + sinA * n2y);
                            const pzKm = baseKmZ + headWidthKm * (cosA * n1z + sinA * n2z);
                            meshX.push(pxKm / kmPerDegLon);
                            meshY.push(pyKm / kmPerDegLat);
                            meshZ.push(pzKm);
                            meshIntensity.push(vectorNum);
                        }

                        // Vertex N_SIDES + 1: Base center (for solid rear cap)
                        meshX.push(bx);
                        meshY.push(by);
                        meshZ.push(bz);
                        meshIntensity.push(vectorNum);

                        // Triangular faces
                        for (let s = 0; s < N_SIDES; s++) {
                            const nextS = (s + 1) % N_SIDES;
                            // Side face (Tip -> s -> nextS)
                            meshI.push(K + 0);
                            meshJ.push(K + 1 + s);
                            meshK.push(K + 1 + nextS);

                            // Base cap face (Base Center -> nextS -> s)
                            meshI.push(K + 1 + N_SIDES);
                            meshJ.push(K + 1 + nextS);
                            meshK.push(K + 1 + s);
                        }
                    }

                    // Arrow stem (from event i to base of arrowhead)
                    lineX.push(x1, stemEndX, null);
                    lineY.push(y1, stemEndY, null);
                    lineZ.push(z1, stemEndZ, null);
                    lineColor.push(vectorNum, vectorNum, vectorNum);
                }

                if (validPairs === 0) {
                    showStatusToast("No valid pairs for event vectors.", false);
                    if (chk) chk.checked = false;
                    if (btn) btn.classList.remove('active');
                    this._activeConsecutiveArrows = false;
                    this.updateSwapLegendVisibility();
                    return;
                }

                this._activeConsecutiveArrows = true;
                this._consecutiveVectorCount = validPairs;
                if (chk) chk.checked = true;

                const vectorScale = (this._layerScales && this._layerScales.vectors) ? this._layerScales.vectors : 'Vectors';
                const lineTrace = {
                    type: 'scatter3d',
                    name: 'Consecutive Event Vectors',
                    x: lineX,
                    y: lineY,
                    z: lineZ,
                    mode: 'lines',
                    line: {
                        color: lineColor,
                        colorscale: getPlotlyScale(vectorScale),
                        cmin: 1,
                        cmax: validPairs,
                        width: 4
                    },
                    hoverinfo: 'skip',
                    showlegend: false
                };

                const tracesToAdd = [lineTrace];

                if (meshX.length > 0) {
                    const arrowMeshTrace = {
                        type: 'mesh3d',
                        name: 'Event Arrowheads',
                        x: meshX,
                        y: meshY,
                        z: meshZ,
                        i: meshI,
                        j: meshJ,
                        k: meshK,
                        intensity: meshIntensity,
                        colorscale: getPlotlyScale(vectorScale),
                        cmin: 1,
                        cmax: validPairs,
                        flatshading: true,
                        lighting: {
                            ambient: 0.85,
                            diffuse: 0.8,
                            specular: 0.15,
                            roughness: 0.5
                        },
                        showscale: false,
                        hoverinfo: 'skip'
                    };
                    tracesToAdd.push(arrowMeshTrace);
                }

                Plotly.addTraces(gd, tracesToAdd);
                if (btn) btn.classList.add('active');

                if (window._currentLegendMode === 'vectors') {
                    updateGlassLegendInternal(true, 'VECTOR N°', 'Vectors', false, [1, validPairs], null);
                }

                this.updateSwapLegendVisibility();
            } else {
                if (chk) chk.checked = false;
                if (btn) btn.classList.remove('active');
                this._activeConsecutiveArrows = false;
                let isClustering = false;
                if (typeof window.animClusteringEnabled !== 'undefined' && window.animClusteringEnabled) {
                    isClustering = true;
                } else if (typeof window.lockedClusters !== 'undefined') {
                    isClustering = true;
                }
                if (window._currentLegendMode === 'vectors') {
                    if (isClustering) {
                        window._currentLegendMode = 'clusters';
                        if (typeof updateClusterLegend === 'function') {
                            if (typeof window._lastPresentLabels !== 'undefined') {
                                updateClusterLegend(window._lastPresentLabels);
                            } else {
                                updateClusterLegend();
                            }
                        }
                    } else {
                        window._currentLegendMode = 'earthquakes';
                        if (window._earthquakeLegendState) {
                            const s = window._earthquakeLegendState;
                            updateGlassLegendInternal(s.show, s.title, s.scaleName, s.invert, s.limits, s.dateInfo);
                        }
                    }
                }
                this.updateSwapLegendVisibility();
            }
        },

        removeConsecutiveArrowTraces(gd) {
            if (!gd || !gd.data) return;
            const indicesToRemove = [];
            for (let i = gd.data.length - 1; i >= 0; i--) {
                const tr = gd.data[i];
                if (tr && (tr.name === 'Consecutive Event Vectors' || tr.name === 'Event Arrowheads')) {
                    indicesToRemove.push(i);
                }
            }
            if (indicesToRemove.length > 0) {
                Plotly.deleteTraces(gd, indicesToRemove);
            }
        },

        updateSwapLegendVisibility() {
            this.updateLegendSwapButtonVisibility();
        },

        setExportFormat(fmt) {
            if (window.SeismicExport) return window.SeismicExport.setExportFormat(fmt);
        },

        exportClustersCSV() {
            if (window.SeismicExport) return window.SeismicExport.exportClustersCSV();
        },

        openClusterCsvPreview(payload) {
            if (window.SeismicExport) return window.SeismicExport.openClusterCsvPreview(payload);
        },

        selectClusterPreviewTab(idx) {
            if (window.SeismicExport) return window.SeismicExport.selectClusterPreviewTab(idx);
        },

        updateClusterExportButtons() {
            if (window.SeismicExport) return window.SeismicExport.updateClusterExportButtons();
        },

        renderClusterPreviewTable() {
            if (window.SeismicExport) return window.SeismicExport.renderClusterPreviewTable();
        },

        closeClusterCsvDialog() {
            if (window.SeismicExport) return window.SeismicExport.closeClusterCsvDialog();
        },

        downloadSelectedClusterCSV() {
            if (window.SeismicExport) return window.SeismicExport.downloadSelectedClusterCSV();
        },

        downloadAllClustersZIP() {
            if (window.SeismicExport) return window.SeismicExport.downloadAllClustersZIP();
        },

        downloadClustersCSV() {
            // Backward compatibility alias for single cluster download
            this.downloadSelectedClusterCSV();
        },

        // Note: Swarms Subsystem methods are implemented in /assets/viz_swarms.js
        openSwarmChartDialog(swarmIndex) {
            if (window.SeismicSwarms && window.SeismicSwarms.openSwarmChartDialog) {
                return window.SeismicSwarms.openSwarmChartDialog.apply(window.SeismicSwarms, arguments);
            }
        },

        closeSwarmChartDialog() {
            if (window.SeismicSwarms && window.SeismicSwarms.closeSwarmChartDialog) {
                return window.SeismicSwarms.closeSwarmChartDialog.apply(window.SeismicSwarms, arguments);
            }
        },

        downloadSwarmChart() {
            if (window.SeismicSwarms && window.SeismicSwarms.downloadSwarmChart) {
                return window.SeismicSwarms.downloadSwarmChart.apply(window.SeismicSwarms, arguments);
            }
        },

        navigateSwarmChart(direction) {
            if (window.SeismicSwarms && window.SeismicSwarms.navigateSwarmChart) {
                return window.SeismicSwarms.navigateSwarmChart.apply(window.SeismicSwarms, arguments);
            }
        },

        // Note: External Layers Subsystem methods are implemented in /assets/viz_layers.js
        toggleLayerModal(e) {
            if (window.SeismicLayers && window.SeismicLayers.toggleLayerModal) {
                return window.SeismicLayers.toggleLayerModal.apply(window.SeismicLayers, arguments);
            }
        },

        selectLayer(layerType) {
            if (window.SeismicLayers && window.SeismicLayers.selectLayer) {
                return window.SeismicLayers.selectLayer.apply(window.SeismicLayers, arguments);
            }
        },

        restoreStoredLayers(attempt) {
            if (window.SeismicLayers && window.SeismicLayers.restoreStoredLayers) {
                return window.SeismicLayers.restoreStoredLayers.apply(window.SeismicLayers, arguments);
            }
        },

        applyAllLayers() {
            if (window.SeismicLayers && window.SeismicLayers.applyAllLayers) {
                return window.SeismicLayers.applyAllLayers.apply(window.SeismicLayers, arguments);
            }
        },

        toggleUpliftSurface() {
            if (window.SeismicLayers && window.SeismicLayers.toggleUpliftSurface) {
                return window.SeismicLayers.toggleUpliftSurface.apply(window.SeismicLayers, arguments);
            }
        },

        toggleTomography() {
            if (window.SeismicLayers && window.SeismicLayers.toggleTomography) {
                return window.SeismicLayers.toggleTomography.apply(window.SeismicLayers, arguments);
            }
        },

        toggleTomographyHigh() {
            if (window.SeismicLayers && window.SeismicLayers.toggleTomographyHigh) {
                return window.SeismicLayers.toggleTomographyHigh.apply(window.SeismicLayers, arguments);
            }
        },

        toggleTomographyLow() {
            if (window.SeismicLayers && window.SeismicLayers.toggleTomographyLow) {
                return window.SeismicLayers.toggleTomographyLow.apply(window.SeismicLayers, arguments);
            }
        },

        toggleStations() {
            if (window.SeismicLayers && window.SeismicLayers.toggleStations) {
                return window.SeismicLayers.toggleStations.apply(window.SeismicLayers, arguments);
            }
        },

        swapLegend() {
            if (window.SeismicLayers && window.SeismicLayers.swapLegend) {
                return window.SeismicLayers.swapLegend.apply(window.SeismicLayers, arguments);
            }
        },

        bringMarkersToFront() {
            if (window.SeismicLayers && typeof window.SeismicLayers.bringMarkersToFront === 'function') {
                return window.SeismicLayers.bringMarkersToFront.apply(window.SeismicLayers, arguments);
            }
            return Promise.resolve();
        },

        handleOverlayUpload(input) {
            if (window.SeismicLayers && window.SeismicLayers.handleOverlayUpload) {
                return window.SeismicLayers.handleOverlayUpload.apply(window.SeismicLayers, arguments);
            }
        },

        restoreOriginalMap() {
            if (window.SeismicLayers && window.SeismicLayers.restoreOriginalMap) {
                return window.SeismicLayers.restoreOriginalMap.apply(window.SeismicLayers, arguments);
            }
        },

        captureScreenshot() {
            if (window.SeismicExport) return window.SeismicExport.captureScreenshot();
        },

        openScreenshotPreview(dataUrl) {
            if (window.SeismicExport) return window.SeismicExport.openScreenshotPreview(dataUrl);
        },

        closeScreenshotPreview() {
            if (window.SeismicExport) return window.SeismicExport.closeScreenshotPreview();
        },

        downloadScreenshot() {
            if (window.SeismicExport && typeof window.SeismicExport.downloadScreenshotPNG === 'function') {
                return window.SeismicExport.downloadScreenshotPNG();
            }
        }
    };
    
    // Esponi SeismicUI globalmente fondendo con i moduli esportati (come viz_export.js)
    window.SeismicUI = Object.assign(window.SeismicUI || {}, SeismicUI);

    document.onclick = () => {
        document.querySelectorAll('.glass-menu').forEach(m => m.classList.remove('show'));
        if (typeof SeismicUI !== 'undefined' && SeismicUI.closeBottomLeftPopups) {
            SeismicUI.closeBottomLeftPopups();
        } else {
            const infoPanel = document.getElementById('info-panel');
            if (infoPanel) infoPanel.classList.remove('show');
            const layerModal = document.getElementById('layer-modal');
            if (layerModal) layerModal.classList.remove('active');
            const exportModal = document.getElementById('export-modal');
            if (exportModal) exportModal.classList.remove('active');
            const shortcutsModal = document.getElementById('shortcuts-modal');
            if (shortcutsModal) shortcutsModal.classList.remove('active');
            const swarmChartDialog = document.getElementById('swarm-chart-dialog');
            if (swarmChartDialog) swarmChartDialog.classList.remove('active');
            const screenshotDialog = document.getElementById('screenshot-preview-dialog');
            if (screenshotDialog) screenshotDialog.classList.remove('active');
            const clusterCsvDialog = document.getElementById('cluster-csv-dialog');
            if (clusterCsvDialog) clusterCsvDialog.classList.remove('active');
        }
    };

    window.addEventListener('scroll', () => {
        document.querySelectorAll('.glass-menu.show').forEach(m => m.classList.remove('show'));
    }, true);

    window.addEventListener('resize', () => {
        document.querySelectorAll('.glass-menu.show').forEach(m => m.classList.remove('show'));
    });



    // Manual loader control only. Templates must call hideInitLoader() explicitly.


    const COLORS_MAP = {
        'Viridis': ['#440154', '#482878', '#3e4989', '#31688e', '#26828e', '#1f9e89', '#6ece58', '#b5de2b', '#fde725'],
        'Plasma': ['#0d0887', '#4b03a1', '#7d03a8', '#a41e9a', '#c33580', '#de4c60', '#f16d41', '#fa9913', '#f6c710', '#eff921'],
        'Inferno': ['#000004', '#160b39', '#420a68', '#6a176e', '#932667', '#bc3754', '#dd513a', '#f37819', '#fca50a', '#f9d22a', '#fcffa4'],

        'Turbo': ['#30123b', '#41459b', '#4675ed', '#419df9', '#2eaede', '#1dbeab', '#24ca70', '#56d445', '#88db32', '#bad928', '#e2c933', '#f8aa31', '#ff842a', '#f75b14', '#e03b07', '#bd2205', '#9a1003', '#7a0403'],
        'Jet': ['#00008f', '#0000ff', '#007fff', '#00ffff', '#7fff7f', '#ffff00', '#ff7f00', '#ff0000', '#7f0000'],
        'Cividis': ['#00224e', '#123570', '#3c4b66', '#6b6d76', '#8e8c82', '#b1ac86', '#d4cd91', '#f8f1ae'],
        'Electric': ['#000000', '#1e008a', '#7d00ba', '#c400b8', '#fe00a2', '#ff5e61', '#ffc100', '#ffff00'],
        'Hot': ['#000000', '#e60000', '#ffcc00', '#ffffff'],
        'Tomography': ['rgb(255, 60, 0)', 'rgb(255, 160, 80)', 'rgb(255, 255, 255)', 'rgb(80, 180, 255)', 'rgb(0, 100, 255)'],
        'Uplift': ['rgb(255, 255, 0)', 'rgb(255, 140, 0)', 'rgb(180, 0, 0)'],
        'Vectors': ['#440154', '#482878', '#3e4989', '#31688e', '#26828e', '#1f9e89', '#6ece58', '#b5de2b', '#fde725']
    };
    window.COLORS_MAP = COLORS_MAP;

    function getPlotlyScale(name) {
        if (Array.isArray(name)) return name;
        const colors = COLORS_MAP[name] || COLORS_MAP['Viridis'];
        return colors.map((c, i) => [i / (colors.length - 1), c]);
    }
    window.getPlotlyScale = getPlotlyScale;


    function updateGlassLegend(show, title, scaleName, invert, limits, dateInfo) {
        if (title === 'Depth' || (typeof title === 'string' && title.toLowerCase() === 'depth')) title = 'Depth (KM)';
        if (scaleName) {
            if (!window.SeismicUI) window.SeismicUI = {};
            if (!window.SeismicUI._layerScales) window.SeismicUI._layerScales = {};
            window.SeismicUI._layerScales.earthquakes = scaleName;
        } else if (window.SeismicUI && window.SeismicUI._layerScales && window.SeismicUI._layerScales.earthquakes) {
            scaleName = window.SeismicUI._layerScales.earthquakes;
        }
        window._earthquakeLegendState = { show, title, scaleName, invert, limits, dateInfo };
        if (!window._currentLegendMode || window._currentLegendMode === 'earthquakes') {
            updateGlassLegendInternal(show, title, scaleName, invert, limits, dateInfo);
        }
    }

    function updateGlassLegendInternal(show, title, scaleName, invert, limits, dateInfo) {
        if (title === 'Depth' || (typeof title === 'string' && title.toLowerCase() === 'depth')) title = 'Depth (KM)';
        const legend = document.getElementById('glass-legend');
        if (!show) { legend.style.display = 'none'; return; }

        legend.style.display = 'flex';
        legend.style.width = '';
        legend.style.minWidth = '';
        legend.style.maxWidth = '';
        legend.style.padding = '';
        document.getElementById('legend-title').textContent = title;

        const bodyWrapper = document.getElementById('legend-body-wrapper');
        if (bodyWrapper) bodyWrapper.style.display = 'flex';
        const legendContainer = document.getElementById('legend-container');
        if (legendContainer) legendContainer.style.display = 'flex';
        const clusterList = document.getElementById('cluster-list');
        if (clusterList) clusterList.style.display = 'none';
        const scaleWrapper = document.getElementById('legend-scale-wrapper');
        if (scaleWrapper) scaleWrapper.style.display = 'flex';

        const scaleToggle = document.getElementById('legend-scale-toggle');
        const scaleSwatch = document.getElementById('legend-scale-swatch');
        const scaleMenu = document.getElementById('legend-scale-menu');
        if (scaleToggle && scaleName) {
            scaleToggle.title = 'Color scale: ' + scaleName;
            if (scaleSwatch) {
                let sColors = COLORS_MAP[scaleName] || COLORS_MAP['Viridis'];
                scaleSwatch.style.background = `linear-gradient(to top, ${sColors.join(',')})`;
            }
            if (scaleMenu) {
                scaleMenu.querySelectorAll('.menu-item').forEach(mi => {
                    if (mi.dataset.val === scaleName) mi.classList.add('active');
                    else mi.classList.remove('active');
                });
            }
        }

        const bar = document.getElementById('legend-bar');
        let colors = COLORS_MAP[scaleName] || COLORS_MAP['Viridis'];
        if (invert) colors = [...colors].reverse();
        bar.style.background = `linear-gradient(to top, ${colors.join(',')})`;

        const ticksContainer = document.getElementById('legend-ticks');
        ticksContainer.innerHTML = '';

        const numTicks = 5;
        const step = (limits[1] - limits[0]) / (numTicks - 1);

        for (let i = numTicks - 1; i >= 0; i--) {
            const val = limits[0] + step * i;
            const tick = document.createElement('div');
            tick.className = 'legend-tick';

            if (title === 'Date' && dateInfo && dateInfo.startDate) {
                const parts = String(dateInfo.startDate).split('-').map(Number);
                const utc = Date.UTC(parts[0], parts[1] - 1, parts[2]) + Math.round(val) * 86400000;
                const d = new Date(utc);
                const day = String(d.getUTCDate()).padStart(2, '0');
                const month = String(d.getUTCMonth() + 1).padStart(2, '0');
                const year = d.getUTCFullYear();
                tick.textContent = `${day}-${month}-${year}`;
            } else if (scaleName === 'Tomography' || title.includes('Tomo')) {
                tick.textContent = val.toFixed(3);
            } else if (scaleName === 'Vectors' || (typeof title === 'string' && (title.includes('Sequence') || title.includes('Vector')))) {
                tick.textContent = Math.round(val);
            } else {
                tick.textContent = val.toFixed(1);
            }
            ticksContainer.appendChild(tick);
        }

        if (window.SeismicUI && typeof window.SeismicUI.updateLegendSwapButtonVisibility === 'function') {
            window.SeismicUI.updateLegendSwapButtonVisibility();
        }
    }

    function showStatusToast(msg, isSuccess = false, timeout = 5000) {
        const container = document.getElementById('toast-container');
        if (!container) return;
        container.innerHTML = ''; // Clear previous notifications
        const toast = document.createElement('div');
        toast.className = 'toast';
        
        let iconHtml = '⚠️ ';
        if (isSuccess === true || (typeof isSuccess === 'string' && (isSuccess === 'success' || isSuccess === 'ok'))) {
            iconHtml = '<span style="color: #10b981; font-weight: bold; font-size: 1.2em;">✓</span> ';
        } else if (isSuccess === false || (typeof isSuccess === 'string' && isSuccess === 'error')) {
            iconHtml = '⚠️ ';
        } else {
            const lowerMsg = String(msg).toLowerCase();
            if (lowerMsg.includes('success') || lowerMsg.includes('saved') || lowerMsg.includes('applied') || lowerMsg.includes('exported') || lowerMsg.includes('selected') || lowerMsg.includes('toggled') || lowerMsg.includes('restored') || lowerMsg.includes('cancelled') || lowerMsg.includes('selecting') || lowerMsg.includes('waiting') || lowerMsg.includes('preparing')) {
                iconHtml = '<span style="color: #10b981; font-weight: bold; font-size: 1.2em;">✓</span> ';
            } else {
                iconHtml = '⚠️ ';
            }
        }

        toast.innerHTML = `<span>${iconHtml}${msg}</span>`;
        container.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, timeout);
    }


    /* ─── Pass-Through Mouse Raycasting for Map Terrain ─── */
    let plotlyId = null;
    let plotlyPollInterval = null;
    let plotlyPollAttempts = 0;

    function setupPassThroughTerrainHover(gd) {
        if (!gd) return;

        function applyTerrainPassThrough() {
            if (!gd._fullLayout) return;
            const subplots = gd._fullLayout._subplots;
            const gl3dList = (subplots && subplots.gl3d) ? subplots.gl3d : ['scene'];

            for (const sName of gl3dList) {
                const sceneLayout = gd._fullLayout[sName];
                const scene = sceneLayout ? sceneLayout._scene : null;
                if (!scene || !scene.glplot) continue;

                // 1. Tag and disable picking on terrain traces via scene.traces
                if (scene.traces) {
                    for (const uid of Object.keys(scene.traces)) {
                        const tr = scene.traces[uid];
                        if (!tr) continue;
                        const trData = tr.data || {};
                        const name = trData.name || '';
                        const type = trData.type || '';
                        const hoverinfo = trData.hoverinfo || '';
                        const isTerrain = name === 'Map Terrain' ||
                                          name.toLowerCase().includes('terrain') ||
                                          type === 'surface' ||
                                          hoverinfo === 'skip';
                        if (isTerrain) {
                            if (tr.surface) {
                                tr.surface._isTerrain = true;
                                tr.surface.drawPick = function() {};
                                tr.surface.pick = function() { return null; };
                            }
                            if (tr.mesh && hoverinfo === 'skip') {
                                tr.mesh._isTerrain = true;
                                tr.mesh.drawPick = function() {};
                                tr.mesh.pick = function() { return null; };
                            }
                            tr.handlePick = function() { return false; };
                        }
                    }
                }

                // 2. Intercept glplot.drawPick to ensure terrain never renders into pick buffer
                if (!scene.glplot._pickPatched) {
                    scene.glplot._pickPatched = true;
                    const origDrawPick = scene.glplot.drawPick;
                    scene.glplot.drawPick = function() {
                        if (this.objects) {
                            for (let n = 0; n < this.objects.length; ++n) {
                                const obj = this.objects[n];
                                if (!obj) continue;
                                const isSurface = obj._isTerrain ||
                                                  (obj.field !== undefined) ||
                                                  (obj.vertexCount !== undefined && obj.pickShader !== undefined && obj.highlight !== undefined);
                                if (isSurface) {
                                    obj._isTerrain = true;
                                    obj.drawPick = function() {};
                                    obj.pick = function() { return null; };
                                }
                            }
                        }
                        return origDrawPick.apply(this, arguments);
                    };
                }

                // 3. Patch any existing objects in scene.glplot.objects right away
                if (scene.glplot.objects) {
                    for (let n = 0; n < scene.glplot.objects.length; ++n) {
                        const obj = scene.glplot.objects[n];
                        if (!obj) continue;
                        const isSurface = obj._isTerrain ||
                                          (obj.field !== undefined) ||
                                          (obj.vertexCount !== undefined && obj.pickShader !== undefined && obj.highlight !== undefined);
                        if (isSurface) {
                            obj._isTerrain = true;
                            obj.drawPick = function() {};
                            obj.pick = function() { return null; };
                        }
                    }
                }
            }
        }

        applyTerrainPassThrough();
        if (typeof gd.on === 'function' && !gd._terrainPassThroughHooked) {
            gd._terrainPassThroughHooked = true;
            gd.on('plotly_afterplot', applyTerrainPassThrough);
            gd.on('plotly_relayout', applyTerrainPassThrough);
            gd.on('plotly_restyle', applyTerrainPassThrough);
            gd.on('plotly_redraw', applyTerrainPassThrough);
            gd.on('plotly_animatingframe', applyTerrainPassThrough);
        }
    }

    function findPlotlyGraph() {
        if (!plotlyId) {
            const gd = document.querySelector('.plotly-graph-div') || document.getElementById('plot') || document.getElementById('plotly-div');
            if (gd && gd.id) {
                plotlyId = gd.id;
            } else if (gd) {
                // If ID is missing, assign a temporary one
                gd.id = 'plotly-graph-gen-' + Math.random().toString(36).substr(2, 9);
                plotlyId = gd.id;
            }
        }

        let isReady = false;
        if (plotlyId) {
            const gd = document.getElementById(plotlyId);
            if (gd) {
                setupPassThroughTerrainHover(gd);
                setupCameraRelayoutWatcher(gd);
                if (gd._fullLayout && gd._fullLayout.scene && gd._fullLayout.scene._scene && gd._fullLayout.scene._scene.glplot) {
                    isReady = true;
                }
            }
        }

        plotlyPollAttempts++;
        if ((isReady || plotlyPollAttempts > 50) && plotlyPollInterval) {
            clearInterval(plotlyPollInterval);
            plotlyPollInterval = null;
        }

        // Camera controls: show glass camera panel in both 2D and 3D views
        const controls = document.getElementById('camera-controls');
        if (controls) {
            controls.style.display = 'flex';
            const gd = plotlyId ? document.getElementById(plotlyId) : null;
            const is3D = Boolean(window.IS_3D_VIEW || (gd && gd.layout && gd.layout.scene));
            const cam3dOnlyEls = controls.querySelectorAll('.cam-3d-only');
            cam3dOnlyEls.forEach(el => {
                el.style.display = is3D ? 'flex' : 'none';
            });
            updatePasteButtonState();
            if (!is3D) {
                const sRowV = document.getElementById('shortcut-row-vectors');
                if (sRowV) sRowV.style.display = 'none';
                const sRowC = document.getElementById('shortcut-row-cinema');
                if (sRowC) sRowC.style.display = 'none';
                const sRowS = document.getElementById('shortcut-row-side');
                if (sRowS) sRowS.style.display = 'none';
            }
        }
    }

    // Camera integration: use SeismicCamera from viz_camera.js
    const cam = window.SeismicCamera || {};
    const snapToView = cam.snapToView || window.snapToView || (() => Promise.resolve());
    const toggleCinemaMode = cam.toggleCinemaMode || window.toggleCinemaMode || (() => {});
    const copyCameraOrientation = cam.copyCameraOrientation || window.copyCameraOrientation || (() => {});
    const pasteCameraOrientation = cam.pasteCameraOrientation || window.pasteCameraOrientation || (() => Promise.resolve());
    const updatePasteButtonState = cam.updatePasteButtonState || window.updatePasteButtonState || (() => {});
    const setupCameraRelayoutWatcher = cam.setupCameraRelayoutWatcher || window.setupCameraRelayoutWatcher || (() => {});

    window.copyCameraOrientation = copyCameraOrientation;
    window.pasteCameraOrientation = pasteCameraOrientation;
    window.updatePasteButtonState = updatePasteButtonState;
    window.snapToView = snapToView;
    window.toggleCinemaMode = toggleCinemaMode;
    window.setupPassThroughTerrainHover = setupPassThroughTerrainHover;
    window.findPlotlyGraph = findPlotlyGraph;

    findPlotlyGraph();
    if (!plotlyPollInterval) {
        plotlyPollInterval = setInterval(findPlotlyGraph, 200);
    }
    if (window.SeismicUI && typeof window.SeismicUI.initLegendScaleMenu === 'function') {
        window.SeismicUI.initLegendScaleMenu();
    }
    window.addEventListener('load', () => {
        findPlotlyGraph();
        if (window.SeismicUI && typeof window.SeismicUI.initLegendScaleMenu === 'function') {
            window.SeismicUI.initLegendScaleMenu();
        }
    });
    setTimeout(() => {
        findPlotlyGraph();
        if (window.SeismicUI && typeof window.SeismicUI.initLegendScaleMenu === 'function') {
            window.SeismicUI.initLegendScaleMenu();
        }
        checkHistoryStatus();
    }, 100); 
    if (window.IS_3D_VIEW === undefined) window.IS_3D_VIEW = true;

    window.addEventListener('pywebviewready', () => {
        if (window.SeismicUI) {
            window.SeismicUI.updateLegendSwapButtonVisibility();
            if (typeof window.SeismicUI.initLegendScaleMenu === 'function') {
                window.SeismicUI.initLegendScaleMenu();
            }
            if (typeof window.SeismicUI.restoreStoredLayers === 'function') {
                window.SeismicUI.restoreStoredLayers();
            }
        }
        checkHistoryStatus();
    });
    setTimeout(() => {
        if (window.pywebview && window.pywebview.api && window.SeismicUI && typeof window.SeismicUI.restoreStoredLayers === 'function') {
            window.SeismicUI.restoreStoredLayers();
        }
        checkHistoryStatus();
    }, 300);

    /* ─── Controls Side Panel Drawer Toggle ─── */
    window.toggleLeftPanel = function() {
        const panel = document.getElementById('left-panel-wrapper');
        if (!panel) return;
        const isCollapsed = panel.classList.toggle('collapsed');
        let expandBtn = document.getElementById('btn-expand-sidebar');
        if (!expandBtn) {
            expandBtn = document.createElement('button');
            expandBtn.id = 'btn-expand-sidebar';
            expandBtn.className = 'glass-panel drawer-tab-btn';
            expandBtn.title = 'Open Controls Panel (F)';
            expandBtn.setAttribute('aria-label', 'Open Controls Panel');
            expandBtn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg><span>Controls</span>';
            expandBtn.onclick = () => window.toggleLeftPanel();
            document.body.appendChild(expandBtn);
        }
        if (isCollapsed) {
            expandBtn.classList.add('show');
        } else {
            expandBtn.classList.remove('show');
        }
    };

    /* ─── Legend Drawer Toggle ─── */
    window.toggleLegendPanel = function() {
        const panel = document.getElementById('glass-legend');
        if (!panel) return;
        const isCollapsed = panel.classList.toggle('collapsed');
        let expandBtn = document.getElementById('btn-expand-legend');
        if (!expandBtn) {
            expandBtn = document.createElement('button');
            expandBtn.id = 'btn-expand-legend';
            expandBtn.className = 'glass-panel drawer-tab-btn-right';
            expandBtn.title = 'Open Legend (L)';
            expandBtn.setAttribute('aria-label', 'Open Legend');
            expandBtn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/></svg><span>Legend</span>';
            expandBtn.onclick = () => window.toggleLegendPanel();
            document.body.appendChild(expandBtn);
        }
        if (isCollapsed) {
            expandBtn.classList.add('show');
        } else {
            expandBtn.classList.remove('show');
        }
    };

    /* ─── Camera Controls Drawer Toggle ─── */
    window.toggleCameraPanel = function() {
        const panel = document.getElementById('camera-controls');
        if (!panel) return;
        const isCollapsed = panel.classList.toggle('collapsed');
        let expandBtn = document.getElementById('btn-expand-camera');
        if (!expandBtn) {
            expandBtn = document.createElement('button');
            expandBtn.id = 'btn-expand-camera';
            expandBtn.className = 'glass-panel drawer-tab-btn-right';
            expandBtn.title = 'Open Camera Controls (K)';
            expandBtn.setAttribute('aria-label', 'Open Camera Controls');
            expandBtn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg><span>Camera</span>';
            expandBtn.onclick = () => window.toggleCameraPanel();
            document.body.appendChild(expandBtn);
        }
        if (isCollapsed) {
            expandBtn.classList.add('show');
        } else {
            expandBtn.classList.remove('show');
        }
    };

    window.toggleRightPanel = function() {
        window.toggleLegendPanel && window.toggleLegendPanel();
        window.toggleCameraPanel && window.toggleCameraPanel();
    };




    /* ─── Global Keyboard Shortcuts ─── */
    window.addEventListener('keydown', (e) => {
        // Prevent accidental page reload in desktop application
        if (e.key === 'F5' || ((e.ctrlKey || e.metaKey) && (e.key === 'r' || e.key === 'R'))) {
            e.preventDefault();
            return;
        }

        // Ignore keystrokes when typing inside inputs, textareas, selects
        const target = e.target;
        const tag = (target && target.tagName) ? target.tagName.toLowerCase() : '';
        if (tag === 'input' || tag === 'textarea' || tag === 'select' || (target && target.isContentEditable)) {
            return;
        }

        // Space: Toggle play/pause for animation
        if (e.code === 'Space') {
            e.preventDefault();
            if (typeof window.togglePlayAnimation === 'function') {
                window.togglePlayAnimation();
            } else {
                const playBtn = document.getElementById('play-btn');
                const pauseBtn = document.getElementById('pause-btn');
                if (playBtn && pauseBtn) {
                    if (playBtn.classList.contains('active') || !pauseBtn.classList.contains('active')) {
                        pauseBtn.click();
                    } else {
                        playBtn.click();
                    }
                } else {
                    const toggleBtn = document.getElementById('btn-play-pause') || 
                                     document.querySelector('.play-btn') || playBtn;
                    if (toggleBtn) toggleBtn.click();
                }
            }
        }
        // R / r: Reset Camera / View
        else if (e.key === 'r' || e.key === 'R') {
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                if (typeof snapToView === 'function') {
                    snapToView('reset');
                    showStatusToast(window.IS_3D_VIEW ? 'Camera reset to default 3D' : 'View reset to default', true);
                }
            }
        }
        // T / t: Top-Down view
        else if (e.key === 't' || e.key === 'T') {
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                if (typeof snapToView === 'function') {
                    snapToView('top');
                    showStatusToast('Top-Down View', true);
                }
            }
        }
        // S / s: Side view
        else if (e.key === 's' || e.key === 'S') {
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                if (typeof snapToView === 'function') {
                    snapToView('side');
                }
            }
        }
        // C / c: Auto-rotation / Cinema mode
        else if (e.key === 'c' || e.key === 'C') {
            if (!e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                if (typeof toggleCinemaMode === 'function') {
                    toggleCinemaMode();
                }
            }
        }
        // V / v or A / a: Toggle Consecutive Event Vectors
        else if (e.key === 'v' || e.key === 'V' || e.key === 'a' || e.key === 'A') {
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                if (!window.IS_3D_VIEW || (typeof is3D !== 'undefined' && !is3D)) {
                    showStatusToast("Event vectors are only available in 3D views.", false);
                    return;
                }
                const evCheck = document.getElementById('event-vectors-check');
                if (evCheck) {
                    evCheck.checked = !evCheck.checked;
                    const applyBtn = document.getElementById('apply-filters-btn') || document.getElementById('apply-all-btn');
                    if (applyBtn) {
                        applyBtn.click();
                    } else if (typeof SeismicUI !== 'undefined' && SeismicUI.toggleConsecutiveArrows) {
                        SeismicUI.toggleConsecutiveArrows(evCheck.checked);
                    }
                } else if (typeof SeismicUI !== 'undefined' && SeismicUI.toggleConsecutiveArrows) {
                    SeismicUI.toggleConsecutiveArrows();
                }
            }
        }
        // Numbers 1 - 4: Fast switch between views
        else if (['1', '2', '3', '4'].includes(e.key)) {
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                const viewMap = {
                    '1': { style: 0, name: '2D Map' },
                    '2': { style: 1, name: '3D Static' },
                    '3': { style: 2, name: '3D Animated' },
                    '4': { style: 3, name: '3D Clustering' }
                };
                const sel = viewMap[e.key];
                if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.load_view === 'function') {
                    e.preventDefault();
                    showStatusToast(`Loading ${sel.name}...`, true);
                    window.pywebview.api.load_view(sel.style);
                }
            }
        }
        // Esc: Close any active popup/modal or return to Hub
        else if (e.key === 'Escape') {
            e.preventDefault();
            const dialogModals = [
                document.getElementById('swarm-chart-dialog'),
                document.getElementById('screenshot-preview-dialog'),
                document.getElementById('cluster-csv-dialog'),
                document.getElementById('shortcuts-modal'),
                document.getElementById('export-modal'),
                document.getElementById('layer-modal')
            ];
            let closedAny = false;
            for (const d of dialogModals) {
                if (d && (d.classList.contains('active') || d.classList.contains('show'))) {
                    d.classList.remove('active');
                    d.classList.remove('show');
                    closedAny = true;
                }
            }
            if (typeof SeismicUI !== 'undefined') {
                if (SeismicUI.closeScreenshotPreview) SeismicUI.closeScreenshotPreview();
                if (SeismicUI.closeClusterCsvDialog) SeismicUI.closeClusterCsvDialog();
                if (SeismicUI.closeSwarmChartDialog) SeismicUI.closeSwarmChartDialog();
            }
            const activePopup = document.querySelector('#info-panel.show, .glass-menu.show');
            if (activePopup) {
                closedAny = true;
            }
            if (typeof SeismicUI !== 'undefined' && SeismicUI.closeBottomLeftPopups) {
                SeismicUI.closeBottomLeftPopups();
            }
            document.querySelectorAll('.glass-menu').forEach(m => m.classList.remove('show'));

            if (closedAny) {
                return;
            }

            if (typeof transitionToHub === 'function') {
                transitionToHub();
            } else if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.go_back === 'function') {
                window.pywebview.api.go_back();
            }
        }
        // F / f: Toggle Controls Drawer
        else if (e.key === 'f' || e.key === 'F') {
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                if (typeof window.toggleLeftPanel === 'function') {
                    window.toggleLeftPanel();
                }
            }
        }
        // I / i: Invert Color Scale
        else if (e.key === 'i' || e.key === 'I') {
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                if (typeof SeismicUI !== 'undefined' && typeof SeismicUI.toggleInvertScale === 'function') {
                    SeismicUI.toggleInvertScale();
                } else {
                    const inv = document.getElementById('invert-scale');
                    if (inv) {
                        inv.checked = !inv.checked;
                        inv.dispatchEvent(new Event('change'));
                    }
                }
            }
        }
        // L / l: Toggle Legend Drawer
        else if (e.key === 'l' || e.key === 'L') {
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                if (typeof window.toggleLegendPanel === 'function') {
                    window.toggleLegendPanel();
                }
            }
        }
        // K / k: Toggle Camera Controls Drawer
        else if (e.key === 'k' || e.key === 'K') {
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                if (typeof window.toggleCameraPanel === 'function') {
                    window.toggleCameraPanel();
                }
            }
        }
        // H / ? / F1: Toggle Keyboard Shortcuts Modal
        else if (e.key === 'h' || e.key === 'H' || e.code === 'KeyH' || e.key === '?' || e.key === 'F1') {
            if (!e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                if (typeof SeismicUI !== 'undefined' && SeismicUI.toggleShortcutsModal) {
                    SeismicUI.toggleShortcutsModal();
                }
            }
        }
    });
