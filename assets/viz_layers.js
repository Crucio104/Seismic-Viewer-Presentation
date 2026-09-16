// --- Seismic Viewer: Modular External Layers Subsystem (Tomography, Uplift, GNSS Stations & Texture Overlay) ---
(function() {
    'use strict';

    const SeismicLayers = {
        _activeTomographyData: null,
        _activeUpliftData: null,
        _pendingStationsPath: null,
        _pendingUpliftPath: null,
        _pendingTomoPath: null,
        _pendingMapFile: null,
        _originalMapData: null,
        _overlayActive: false,

        toggleLayerModal(e) {
            if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
            const modal = document.getElementById('layer-modal');
            if (modal) {
                const isShowing = modal.classList.contains('active');
                document.querySelectorAll('.glass-menu').forEach(m => m.classList.remove('show'));
                if (window.SeismicUI && typeof window.SeismicUI.closeBottomLeftPopups === 'function') {
                    window.SeismicUI.closeBottomLeftPopups('layer-modal');
                }

                if (!isShowing) {
                    this.restoreStoredLayers();
                    modal.classList.add('active');
                } else {
                    modal.classList.remove('active');
                }
            }
        },

        selectLayer(layerType) {
            if (layerType === 'map') {
                const inp = document.getElementById('overlay-input');
                if (inp) inp.click();
            } else if (layerType === 'stations' || layerType === 'uplift' || layerType === 'tomography') {
                const api = typeof getBridgeApi === 'function' ? getBridgeApi() : (window.getBridgeApi ? window.getBridgeApi() : null);
                if (!api || !api.select_layer_file) {
                    if (typeof showStatusToast === 'function') showStatusToast('Bridge API not available', false);
                    return;
                }
                const self = this;
                api.select_layer_file(layerType).then((res) => {
                    if (res && res.status === 'success') {
                        if (layerType === 'stations') {
                            self._pendingStationsPath = res.path;
                            if (window.SeismicLayers) window.SeismicLayers._pendingStationsPath = res.path;
                            if (window.SeismicUI) window.SeismicUI._pendingStationsPath = res.path;
                            const statusEl = document.getElementById('status-layer-stations');
                            if (statusEl) {
                                statusEl.textContent = res.filename;
                                statusEl.style.color = '#10b981';
                            }
                            const btn = document.getElementById('btn-layer-stations');
                            if (btn) btn.classList.add('selected');
                            if (typeof showStatusToast === 'function') showStatusToast(`Stations CSV selected: ${res.filename}`, true);
                        } else if (layerType === 'uplift') {
                            self._pendingUpliftPath = res.path;
                            if (window.SeismicLayers) window.SeismicLayers._pendingUpliftPath = res.path;
                            if (window.SeismicUI) window.SeismicUI._pendingUpliftPath = res.path;
                            const statusEl = document.getElementById('status-layer-uplift');
                            if (statusEl) {
                                statusEl.textContent = res.filename;
                                statusEl.style.color = '#10b981';
                            }
                            const btn = document.getElementById('btn-layer-uplift');
                            if (btn) btn.classList.add('selected');
                            if (typeof showStatusToast === 'function') showStatusToast(`Uplift CSV selected: ${res.filename}`, true);
                        } else if (layerType === 'tomography') {
                            self._pendingTomoPath = res.path;
                            if (window.SeismicLayers) window.SeismicLayers._pendingTomoPath = res.path;
                            if (window.SeismicUI) window.SeismicUI._pendingTomoPath = res.path;
                            const statusEl = document.getElementById('status-layer-tomo');
                            if (statusEl) {
                                statusEl.textContent = res.filename;
                                statusEl.style.color = '#10b981';
                            }
                            const btn = document.getElementById('btn-layer-tomo');
                            if (btn) btn.classList.add('selected');
                            if (typeof showStatusToast === 'function') showStatusToast(`Tomography CSV selected: ${res.filename}`, true);
                        }
                    } else if (res && res.message) {
                        if (typeof showStatusToast === 'function') showStatusToast(res.message, false);
                    }
                }).catch((err) => {
                    console.error('[LayerModal] Error selecting file:', err);
                    if (typeof showStatusToast === 'function') showStatusToast('Error during file selection', false);
                });
            }
        },

        restoreStoredLayers(attempt = 0) {
            const api = typeof getBridgeApi === 'function' ? getBridgeApi() : (window.getBridgeApi ? window.getBridgeApi() : null);
            if (!api || !api.get_stored_layer_paths) {
                if (attempt < 8) setTimeout(() => this.restoreStoredLayers(attempt + 1), 300);
                return;
            }
            const self = this;
            api.get_stored_layer_paths().then((stored) => {
                if (!stored) return;
                if (stored.stations && stored.stations.path) {
                    self._pendingStationsPath = stored.stations.path;
                    if (window.SeismicLayers) window.SeismicLayers._pendingStationsPath = stored.stations.path;
                    if (window.SeismicUI) window.SeismicUI._pendingStationsPath = stored.stations.path;
                    const statusEl = document.getElementById('status-layer-stations');
                    if (statusEl) {
                        statusEl.textContent = stored.stations.filename;
                        statusEl.style.color = '#10b981';
                    }
                    const btn = document.getElementById('btn-layer-stations');
                    if (btn) btn.classList.add('selected');
                }
                if (stored.uplift && stored.uplift.path) {
                    self._pendingUpliftPath = stored.uplift.path;
                    if (window.SeismicLayers) window.SeismicLayers._pendingUpliftPath = stored.uplift.path;
                    if (window.SeismicUI) window.SeismicUI._pendingUpliftPath = stored.uplift.path;
                    const statusEl = document.getElementById('status-layer-uplift');
                    if (statusEl) {
                        statusEl.textContent = stored.uplift.filename;
                        statusEl.style.color = '#10b981';
                    }
                    const btn = document.getElementById('btn-layer-uplift');
                    if (btn) btn.classList.add('selected');
                }
                if (stored.tomography && stored.tomography.path) {
                    self._pendingTomoPath = stored.tomography.path;
                    if (window.SeismicLayers) window.SeismicLayers._pendingTomoPath = stored.tomography.path;
                    if (window.SeismicUI) window.SeismicUI._pendingTomoPath = stored.tomography.path;
                    const statusEl = document.getElementById('status-layer-tomo');
                    if (statusEl) {
                        statusEl.textContent = stored.tomography.filename;
                        statusEl.style.color = '#10b981';
                    }
                    const btn = document.getElementById('btn-layer-tomo');
                    if (btn) btn.classList.add('selected');
                }
            }).catch(err => console.error('[LayerModal] Error restoring stored layers:', err));
        },

        applyAllLayers() {
            const gd = document.querySelector('.plotly-graph-div');
            if (!gd) return;

            // 1. Apply map file if present
            if (this._pendingMapFile) {
                this._applyMapFile(this._pendingMapFile);
            }

            const upliftPath = this._pendingUpliftPath || (window.SeismicLayers && window.SeismicLayers._pendingUpliftPath) || (window.SeismicUI && window.SeismicUI._pendingUpliftPath) || "";
            const tomoPath = this._pendingTomoPath || (window.SeismicLayers && window.SeismicLayers._pendingTomoPath) || (window.SeismicUI && window.SeismicUI._pendingTomoPath) || "";
            const stationsPath = this._pendingStationsPath || (window.SeismicLayers && window.SeismicLayers._pendingStationsPath) || (window.SeismicUI && window.SeismicUI._pendingStationsPath) || "";

            // 2. Apply Uplift, Tomography, Stations if present
            if (upliftPath || tomoPath || stationsPath) {
                const api = typeof getBridgeApi === 'function' ? getBridgeApi() : (window.getBridgeApi ? window.getBridgeApi() : null);
                if (!api || !api.apply_external_layers) return;
                const isMapbox = gd && (gd.data && gd.data.some(tr => tr.type === 'scattermapbox' || tr.type === 'densitymapbox' || tr.type === 'scattermap' || tr.type === 'densitymap') || (gd.layout && (gd.layout.mapbox || gd.layout.map)));
                const loader = document.getElementById('loader');
                const loaderText = loader ? loader.querySelector('.loader-text') : null;
                if (loaderText) loaderText.textContent = isMapbox ? 'Applying 2D layers...' : 'Applying 3D layers...';
                if (loader) loader.classList.add('show');

                const self = this;
                api.apply_external_layers({
                    uplift_path: upliftPath,
                    tomography_path: tomoPath,
                    stations_path: stationsPath
                }).then((res) => {
                    if (loader) loader.classList.remove('show');
                    if (res && res.status === 'success') {
                        const layers = res.layers || res;
                        const newTraces = [];
                        const t = layers.tomography || res.tomography;
                        if (t && t.error) {
                            if (typeof showStatusToast === 'function') showStatusToast('Tomography Error: ' + t.error, false);
                        } else if (t && (t.x || t.lons)) {
                            self._activeTomographyData = t;
                            if (window.SeismicLayers) window.SeismicLayers._activeTomographyData = t;
                            if (window.SeismicUI) window.SeismicUI._activeTomographyData = t;
                            self._setupTomography2DControls(t);
                            if (!isMapbox) {
                                const isoGrid = t.iso_grid;
                                if (isoGrid && isoGrid.x && isoGrid.x.length > 0) {
                                    const minVpVs = (isoGrid.min_val !== undefined && !isNaN(isoGrid.min_val)) ? isoGrid.min_val : 0.68;
                                    const maxVpVs = (isoGrid.max_val !== undefined && !isNaN(isoGrid.max_val)) ? isoGrid.max_val : 2.85;

                                    let neutralRef = 1.75;
                                    const neutralInputEl = document.getElementById('tomo-neutral-input');
                                    if (neutralInputEl && neutralInputEl.value) {
                                        const parsedNeut = parseFloat(neutralInputEl.value);
                                        if (!isNaN(parsedNeut) && parsedNeut >= 1.2 && parsedNeut <= 2.5) {
                                            neutralRef = parsedNeut;
                                        }
                                    }

                                    const globalTomoColorScale = [
                                        [0.0, 'rgb(255, 20, 0)'],
                                        [0.35, 'rgb(255, 140, 40)'],
                                        [0.5, 'rgb(245, 245, 245)'],
                                        [0.65, 'rgb(80, 180, 255)'],
                                        [1.0, 'rgb(0, 80, 255)']
                                    ];

                                    newTraces.push({
                                        type: 'volume',
                                        name: `Tomography High Vp/Vs (> ${neutralRef.toFixed(2)})`,
                                        visible: true,
                                        x: isoGrid.x,
                                        y: isoGrid.y,
                                        z: isoGrid.z,
                                        value: isoGrid.value,
                                        isomin: neutralRef + 0.01,
                                        isomax: Math.max(maxVpVs, neutralRef + 0.05),
                                        cmin: 1.15,
                                        cmax: 2.35,
                                        opacity: 0.65,
                                        surface: { show: true, count: 12, fill: 1.0 },
                                        spaceframe: { show: true, fill: 1.0 },
                                        caps: { x: { show: true, fill: 1.0 }, y: { show: true, fill: 1.0 }, z: { show: true, fill: 1.0 } },
                                        colorscale: globalTomoColorScale,
                                        reversescale: false,
                                        showscale: false,
                                        showlegend: true,
                                        hoverinfo: 'skip'
                                    });

                                    newTraces.push({
                                        type: 'volume',
                                        name: `Tomography Low Vp/Vs (< ${neutralRef.toFixed(2)})`,
                                        visible: true,
                                        x: isoGrid.x,
                                        y: isoGrid.y,
                                        z: isoGrid.z,
                                        value: isoGrid.value,
                                        isomin: Math.min(minVpVs, neutralRef - 0.05),
                                        isomax: neutralRef - 0.01,
                                        cmin: 1.15,
                                        cmax: 2.35,
                                        opacity: 0.65,
                                        surface: { show: true, count: 12, fill: 1.0 },
                                        spaceframe: { show: true, fill: 1.0 },
                                        caps: { x: { show: true, fill: 1.0 }, y: { show: true, fill: 1.0 }, z: { show: true, fill: 1.0 } },
                                        colorscale: globalTomoColorScale,
                                        reversescale: false,
                                        showscale: false,
                                        showlegend: true,
                                        hoverinfo: 'skip'
                                    });
                                }
                            } else {
                                let neutralRef = 1.75;
                                const neutralInputEl = document.getElementById('tomo-neutral-input');
                                if (neutralInputEl && neutralInputEl.value) {
                                    const parsedNeut = parseFloat(neutralInputEl.value);
                                    if (!isNaN(parsedNeut) && parsedNeut >= 1.2 && parsedNeut <= 2.5) {
                                        neutralRef = parsedNeut;
                                    }
                                }
                                const sliceTraces = self._buildTomographySliceTraces(null, neutralRef, true, true);
                                sliceTraces.forEach(tr => newTraces.push(tr));
                            }
                            const toggleTomoBtn = document.getElementById('btn-toggle-tomo-points');
                            if (toggleTomoBtn) {
                                toggleTomoBtn.classList.add('visible');
                                toggleTomoBtn.classList.add('active');
                                toggleTomoBtn.innerHTML = 'Toggle Tomography (ON)';
                            }
                            const tomoHighBtn = document.getElementById('btn-toggle-tomo-high');
                            if (tomoHighBtn) {
                                tomoHighBtn.classList.add('visible');
                                tomoHighBtn.classList.add('active');
                                tomoHighBtn.innerHTML = 'High (ON)';
                            }
                            const tomoLowBtn = document.getElementById('btn-toggle-tomo-low');
                            if (tomoLowBtn) {
                                tomoLowBtn.classList.add('visible');
                                tomoLowBtn.classList.add('active');
                                tomoLowBtn.innerHTML = 'Low (ON)';
                            }
                        }
                        const u = layers.uplift || res.uplift;
                        if (u && u.error) {
                            if (typeof showStatusToast === 'function') showStatusToast('Uplift Error: ' + u.error, false);
                        } else if (u && u.lats && u.lons && u.lats.length > 0) {
                            self._activeUpliftData = u;
                            if (window.SeismicLayers) window.SeismicLayers._activeUpliftData = u;
                            if (window.SeismicUI) window.SeismicUI._activeUpliftData = u;
                            if (isMapbox) {
                                const upTraces = self._buildUplift2DTraces(u, true);
                                upTraces.forEach(tr => newTraces.push(tr));
                                
                                const toggleBtn = document.getElementById('btn-toggle-uplift-surface');
                                if (toggleBtn) {
                                    toggleBtn.classList.add('visible');
                                    toggleBtn.classList.add('active');
                                    toggleBtn.innerHTML = 'Toggle Uplift (ON)';
                                }
                            } else {
                                if (u.lines && (u.lines.x || u.lons)) {
                                    newTraces.push({
                                        type: 'scatter3d',
                                        name: 'GNSS Uplift Columns',
                                        x: u.lines.x || u.lons,
                                        y: u.lines.y || u.lats,
                                        z: u.lines.z || u.z_scaled,
                                        mode: 'lines+markers',
                                        hovertext: u.lines.hover || [],
                                        hovertemplate: '%{hovertext}<extra></extra>',
                                        line: { color: '#ef4444', width: 8 },
                                        marker: { size: 6, color: '#ef4444' }
                                    });
                                }
                                if (u.interp_grid && u.interp_grid.grid_lons_2d) {
                                    newTraces.push({
                                        type: 'surface',
                                        name: 'Uplift Interpolated Surface',
                                        x: u.interp_grid.grid_lons_2d,
                                        y: u.interp_grid.grid_lats_2d,
                                        z: u.interp_grid.grid_z_2d,
                                        surfacecolor: u.interp_grid.grid_up_2d,
                                        colorscale: [
                                            [0.0, 'rgb(255, 255, 0)'],
                                            [0.5, 'rgb(255, 140, 0)'],
                                            [1.0, 'rgb(139, 0, 0)']
                                        ],
                                        showscale: false,
                                        opacity: 0.7,
                                        hoverinfo: 'skip',
                                        visible: true
                                    });
                                }
                                const toggleBtn = document.getElementById('btn-toggle-uplift-surface');
                                if (toggleBtn) {
                                    toggleBtn.classList.add('visible');
                                    toggleBtn.classList.add('active');
                                    toggleBtn.innerHTML = 'Toggle Uplift (ON)';
                                }
                            }
                        }
                        const s = layers.stations || res.stations;
                        if (s && s.error) {
                            if (typeof showStatusToast === 'function') showStatusToast('Stations Error: ' + s.error, false);
                        } else if (s && s.lats && s.lons && s.lats.length > 0) {
                            if (isMapbox) {
                                const mapScatterType = (gd.layout && gd.layout.mapbox && !gd.layout.map) ? 'scattermapbox' : 'scattermap';
                                newTraces.push({
                                    type: mapScatterType,
                                    name: 'Stations Outline',
                                    lat: s.lats,
                                    lon: s.lons,
                                    mode: 'markers',
                                    hoverinfo: 'skip',
                                    visible: true,
                                    opacity: 1.0,
                                    marker: {
                                        size: 18,
                                        color: '#000000',
                                        opacity: 1.0
                                    }
                                });
                                newTraces.push({
                                    type: mapScatterType,
                                    name: 'Stations',
                                    lat: s.lats,
                                    lon: s.lons,
                                    mode: 'markers',
                                    hovertext: s.hover || [],
                                    hovertemplate: '%{hovertext}<extra></extra>',
                                    visible: true,
                                    opacity: 1.0,
                                    marker: {
                                        size: 14,
                                        color: '#00ffcc',
                                        opacity: 1.0,
                                        line: { color: '#000000', width: 2 }
                                    }
                                });
                            } else {
                                newTraces.push({
                                    type: 'scatter3d',
                                    name: 'Stations Outline',
                                    x: s.lons,
                                    y: s.lats,
                                    z: s.z || s.lats.map(() => 0),
                                    mode: 'markers',
                                    hoverinfo: 'skip',
                                    visible: true,
                                    opacity: 1.0,
                                    marker: {
                                        size: 8,
                                        color: '#000000',
                                        opacity: 1.0
                                    }
                                });
                                newTraces.push({
                                    type: 'scatter3d',
                                    name: 'Stations',
                                    x: s.lons,
                                    y: s.lats,
                                    z: s.z || s.lats.map(() => 0),
                                    mode: 'markers',
                                    hovertext: s.hover || [],
                                    hovertemplate: '%{hovertext}<extra></extra>',
                                    visible: true,
                                    marker: {
                                        size: 6,
                                        color: '#00ffcc',
                                        opacity: 1.0,
                                        line: { color: '#000000', width: 2 }
                                    }
                                });
                            }
                            const toggleStBtn = document.getElementById('btn-toggle-stations');
                            if (toggleStBtn) {
                                toggleStBtn.classList.add('visible');
                                toggleStBtn.classList.add('active');
                                toggleStBtn.innerHTML = 'Toggle Stations (ON)';
                            }
                        }
                        if (newTraces.length > 0) {
                            const gd = document.querySelector('.plotly-graph-div');
                            if (gd && gd.data) {
                                const indicesToDelete = [];
                                gd.data.forEach((tr, idx) => {
                                    if (tr.name && (tr.name.includes('Tomography') || tr.name.includes('Tomografia') || tr.name.includes('Vp/Vs') || tr.name.includes('Anomaly') || tr.name.includes('Halo') || tr.name === 'GNSS Uplift Columns' || tr.name === 'Uplift' || tr.name === 'Uplift Surface' || tr.name === 'GNSS Uplift Stations' || tr.name === 'Uplift Interpolated Field' || tr.name === 'Uplift Interpolated Surface' || tr.name === 'Stations' || tr.name === 'Stations Outline')) {
                                        indicesToDelete.push(idx);
                                    }
                                });

                                if (indicesToDelete.length > 0) {
                                    try {
                                        Plotly.deleteTraces(gd, indicesToDelete);
                                    } catch (delErr) {
                                        console.warn('[LayerModal] Warning deleting traces:', delErr);
                                    }
                                }

                                Plotly.addTraces(gd, newTraces).then(() => {
                                    const bringFn = (self && typeof self.bringMarkersToFront === 'function')
                                        ? self.bringMarkersToFront.bind(self)
                                        : ((window.SeismicLayers && typeof window.SeismicLayers.bringMarkersToFront === 'function')
                                            ? window.SeismicLayers.bringMarkersToFront.bind(window.SeismicLayers)
                                            : ((window.SeismicUI && typeof window.SeismicUI.bringMarkersToFront === 'function')
                                                ? window.SeismicUI.bringMarkersToFront.bind(window.SeismicUI)
                                                : () => Promise.resolve()));
                                    return Promise.resolve(bringFn());
                                }).then(() => {
                                    if (isMapbox) {
                                        if (typeof Plotly.Plots.resize === 'function') {
                                            Plotly.Plots.resize(gd);
                                        }
                                    } else if (self._activeTomographyData) {
                                        const terrainIdx = gd.data.findIndex(tr => tr && (tr.name === 'Map Terrain' || (tr.type === 'surface' && tr.name && tr.name.includes('Terrain'))));
                                        if (terrainIdx !== -1) {
                                            Plotly.restyle(gd, { opacity: 0.35 }, [terrainIdx]);
                                        }
                                        let maxZ = 0;
                                        let minZ = 0;
                                        if (gd.data) {
                                            gd.data.forEach(tr => {
                                                if (tr.visible !== false && tr.z && Array.isArray(tr.z)) {
                                                    tr.z.forEach(val => {
                                                        if (val !== null && val !== undefined && !isNaN(val)) {
                                                            if (val > maxZ) maxZ = val;
                                                            if (val < minZ) minZ = val;
                                                        }
                                                    });
                                                }
                                            });
                                        }
                                        if (maxZ > 0 && gd.layout && gd.layout.scene && gd.layout.scene.zaxis) {
                                            const currentMin = (gd.layout.scene.zaxis.range && gd.layout.scene.zaxis.range[0] !== undefined)
                                                ? gd.layout.scene.zaxis.range[0] : minZ;
                                            Plotly.relayout(gd, { 'scene.zaxis.range': [currentMin, Math.max(maxZ * 1.15, 0.5)] });
                                        }
                                    }
                                    if (typeof showStatusToast === 'function') showStatusToast('Layers applied successfully!', true);
                                    if (typeof self.updateLegendSwapButtonVisibility === 'function') {
                                        self.updateLegendSwapButtonVisibility();
                                    } else if (window.SeismicUI && typeof window.SeismicUI.updateLegendSwapButtonVisibility === 'function') {
                                        window.SeismicUI.updateLegendSwapButtonVisibility();
                                    }
                                }).catch(err => {
                                    console.error('[LayerModal] Error adding traces:', err);
                                    if (typeof showStatusToast === 'function') {
                                        showStatusToast('Error applying layers: ' + (err?.message || err), false);
                                    }
                                });
                            }
                        }
                    } else if (res && (res.message || res.error)) {
                        if (typeof showStatusToast === 'function') showStatusToast('Error: ' + (res.message || res.error), false);
                    }
                }).catch((err) => {
                    if (loader) loader.classList.remove('show');
                    console.error('[LayerModal] Error applying layers:', err);
                    if (typeof showStatusToast === 'function') {
                        showStatusToast('Error applying layers: ' + (err?.message || err), false);
                    }
                });
            }

            this.toggleLayerModal();
        },

        _setupTomography2DControls(t) {
            const gd = document.querySelector('.plotly-graph-div');
            const isMapboxView = gd && ((gd.data && gd.data.some(tr => tr.type === 'scattermapbox' || tr.type === 'densitymapbox' || tr.type === 'scattermap' || tr.type === 'densitymap')) || (gd.layout && (gd.layout.mapbox || gd.layout.map)));
            let tomoGroup = document.getElementById('tomo-depth-filter-group');
            let neutralGroup = document.getElementById('tomo-neutral-filter-group');
            const settingsBar = document.getElementById('settings-bar');
            if (!settingsBar) return;

            if (isMapboxView) {
                if (neutralGroup) neutralGroup.style.display = 'none';
                if (!tomoGroup) {
                    tomoGroup = document.createElement('div');
                    tomoGroup.id = 'tomo-depth-filter-group';
                    tomoGroup.className = 'settings-group';
                    
                    tomoGroup.innerHTML = `
                        <label class="label" for="tomo-depth-input">Tomography Slice Depth (km)</label>
                        <div class="settings-row">
                            <input type="number" class="glass-input" id="tomo-depth-input" step="0.5" placeholder="Depth (km)">
                        </div>
                    `;
                    
                    const applyBtn = settingsBar.querySelector('#apply-filters-btn') || settingsBar.querySelector('#apply-all-btn') || settingsBar.querySelector('#apply-btn');
                    if (applyBtn && applyBtn.parentNode === settingsBar) {
                        settingsBar.insertBefore(tomoGroup, applyBtn);
                    } else if (applyBtn && applyBtn.parentNode && applyBtn.parentNode.parentNode === settingsBar) {
                        settingsBar.insertBefore(tomoGroup, applyBtn.parentNode);
                    } else {
                        settingsBar.appendChild(tomoGroup);
                    }

                    const inputEl = document.getElementById('tomo-depth-input');
                    if (inputEl) {
                        inputEl.addEventListener('change', (e) => {
                            if (window.SeismicUI && typeof window.SeismicUI.updateTomographySlice === 'function') {
                                window.SeismicUI.updateTomographySlice(e.target.value);
                            }
                        });
                        inputEl.addEventListener('input', (e) => {
                            if (window.SeismicUI && typeof window.SeismicUI.updateTomographySlice === 'function') {
                                window.SeismicUI.updateTomographySlice(e.target.value);
                            }
                        });
                    }
                }
                
                const depths = t.z || t.depths || [];
                const uniqueDepths = (t.unique_depths && t.unique_depths.length > 0) 
                    ? t.unique_depths 
                    : (depths.length > 0 ? Array.from(new Set(depths.map(d => Math.round(Math.abs(d) * 100) / 100))).sort((a, b) => a - b) : []);
                if (uniqueDepths.length > 0) {
                    const inputEl = document.getElementById('tomo-depth-input');
                    if (inputEl) {
                        inputEl.value = uniqueDepths[0];
                    }
                }
                tomoGroup.style.display = 'block';
            } else {
                if (tomoGroup) tomoGroup.style.display = 'none';
                if (!neutralGroup) {
                    neutralGroup = document.createElement('div');
                    neutralGroup.id = 'tomo-neutral-filter-group';
                    neutralGroup.className = 'settings-group';
                    neutralGroup.innerHTML = `
                        <label class="label" for="tomo-neutral-input">Neutral Vp/Vs Ref</label>
                        <div class="settings-row">
                            <input type="number" class="glass-input" id="tomo-neutral-input" step="0.01" value="1.75" placeholder="1.75">
                        </div>
                    `;
                    const applyBtn = settingsBar.querySelector('#apply-filters-btn') || settingsBar.querySelector('#apply-all-btn') || settingsBar.querySelector('#apply-btn');
                    if (applyBtn && applyBtn.parentNode === settingsBar) {
                        settingsBar.insertBefore(neutralGroup, applyBtn);
                    } else if (applyBtn && applyBtn.parentNode && applyBtn.parentNode.parentNode === settingsBar) {
                        settingsBar.insertBefore(neutralGroup, applyBtn.parentNode);
                    } else {
                        settingsBar.appendChild(neutralGroup);
                    }

                    const inputEl = document.getElementById('tomo-neutral-input');
                    if (inputEl) {
                        inputEl.addEventListener('change', (e) => {
                            if (window.SeismicUI && typeof window.SeismicUI.updateTomographyNeutral === 'function') {
                                window.SeismicUI.updateTomographyNeutral(e.target.value);
                            }
                        });
                    }
                }
                neutralGroup.style.display = 'block';
            }
        },

        _buildUplift2DTraces(u, isVisible = true) {
            const gd = document.querySelector('.plotly-graph-div');
            if (!u) u = this._activeUpliftData;
            if (!u || !u.lats || !u.lons || u.lats.length === 0) return [];

            const lats = u.lats;
            const lons = u.lons;
            const upVals = u.up_m || u.up_m_list || [];
            if (upVals.length === 0) return [];

            let minLat = 999, maxLat = -999, minLon = 999, maxLon = -999;
            for (let i = 0; i < lats.length; i++) {
                if (lats[i] < minLat) minLat = lats[i];
                if (lats[i] > maxLat) maxLat = lats[i];
                if (lons[i] < minLon) minLon = lons[i];
                if (lons[i] > maxLon) maxLon = lons[i];
            }
            minLat -= 0.015; maxLat += 0.015;
            minLon -= 0.015; maxLon += 0.015;

            let minVal = 9999, maxVal = -9999;
            for (let i = 0; i < upVals.length; i++) {
                if (upVals[i] < minVal) minVal = upVals[i];
                if (upVals[i] > maxVal) maxVal = upVals[i];
            }
            if (minVal === 9999) { minVal = 0.0; maxVal = 0.08; }
            if (maxVal - minVal < 1e-6) maxVal = minVal + 0.01;

            const meanLat = (minLat + maxLat) / 2;
            const kx = 111.13 * Math.cos(meanLat * Math.PI / 180);
            const ky = 111.13;
            const stKmX = [];
            const stKmY = [];
            for (let s = 0; s < lats.length; s++) {
                stKmX.push(lons[s] * kx);
                stKmY.push(lats[s] * ky);
            }

            const N = 36, M = 36;
            const latStep = (maxLat - minLat) / N;
            const lonStep = (maxLon - minLon) / M;

            const features = [];
            const locs = [];
            const cellVals = [];
            const cellHovers = [];

            for (let r = 0; r < N; r++) {
                const lat1 = minLat + r * latStep;
                const lat2 = minLat + (r + 1) * latStep;
                const cLat = (lat1 + lat2) / 2;
                const cY = cLat * ky;

                for (let c = 0; c < M; c++) {
                    const lon1 = minLon + c * lonStep;
                    const lon2 = minLon + (c + 1) * lonStep;
                    const cLon = (lon1 + lon2) / 2;
                    const cX = cLon * kx;

                    let sumW = 0, sumWV = 0;
                    for (let s = 0; s < lats.length; s++) {
                        const dx = cX - stKmX[s];
                        const dy = cY - stKmY[s];
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        const w = 1.0 / Math.pow(Math.max(dist, 0.0001), 2.5);
                        sumW += w;
                        sumWV += w * upVals[s];
                    }
                    const interpUp = sumWV / sumW;
                    const cellId = 'u_' + (r * M + c);

                    features.push({
                        type: 'Feature',
                        id: cellId,
                        properties: { id: cellId },
                        geometry: {
                            type: 'Polygon',
                            coordinates: [[[lon1, lat1], [lon2, lat1], [lon2, lat2], [lon1, lat2], [lon1, lat1]]]
                        }
                    });
                    locs.push(cellId);
                    cellVals.push(interpUp);
                    cellHovers.push(`<b>Interpolated Uplift Surface</b><br>Value: ${(interpUp * 1000).toFixed(1)} mm (${interpUp.toFixed(4)} m)<br>Lat: ${cLat.toFixed(4)}°, Lon: ${cLon.toFixed(4)}°`);
                }
            }

            const isMap = (gd && gd.layout && gd.layout.map) || (gd && gd.data && gd.data.some(tr => tr.type === 'scattermap' || tr.type === 'choroplethmap'));
            const choroType = isMap ? 'choroplethmap' : 'choroplethmapbox';
            const scatterType = isMap ? 'scattermap' : 'scattermapbox';

            const choroTrace = {
                type: choroType,
                name: 'Uplift Interpolated Surface',
                geojson: {
                    type: 'FeatureCollection',
                    features: features
                },
                locations: locs,
                z: cellVals,
                zmin: minVal,
                zmax: maxVal,
                below: "",
                hovertext: cellHovers,
                hovertemplate: '%{hovertext}<extra></extra>',
                visible: isVisible,
                opacity: 0.72,
                colorscale: [
                    [0.0, 'rgb(255, 255, 0)'],
                    [0.35, 'rgb(255, 140, 0)'],
                    [0.7, 'rgb(220, 38, 38)'],
                    [1.0, 'rgb(127, 29, 29)']
                ],
                showscale: false,
                marker: {
                    opacity: 0.72,
                    line: { width: 0.8, color: 'rgba(255, 255, 255, 0.3)' }
                }
            };

            const stations = u.stations || [];
            const dates = u.dates || [];
            const stationHovers = [];
            for (let i = 0; i < lats.length; i++) {
                const stName = stations[i] || `Station ${i + 1}`;
                const upVal = upVals[i] || 0;
                const dt = dates[i] || '';
                stationHovers.push(`<b>GNSS Station: ${stName}</b><br>Uplift: ${(upVal * 1000).toFixed(1)} mm (${upVal.toFixed(4)} m)<br>Date: ${dt}<br>Lat: ${lats[i].toFixed(4)}°, Lon: ${lons[i].toFixed(4)}°`);
            }

            const gnssTrace = {
                type: scatterType,
                name: 'GNSS Uplift Stations',
                lat: lats,
                lon: lons,
                mode: 'markers',
                hovertext: stationHovers,
                hovertemplate: '%{hovertext}<extra></extra>',
                visible: isVisible,
                opacity: 1.0,
                marker: {
                    size: 9,
                    color: '#ffffff',
                    opacity: 1.0,
                    line: { color: '#b91c1c', width: 2.5 }
                }
            };

            return [choroTrace, gnssTrace];
        },

        _createUplift2DTrace(u) {
            const traces = this._buildUplift2DTraces(u, true);
            return traces.length > 0 ? traces[0] : null;
        },

        _createGNSSStations2DTrace(u) {
            const traces = this._buildUplift2DTraces(u, true);
            return traces.length > 1 ? traces[1] : null;
        },

        _buildTomographySliceTraces(targetDepth, neutralRef, isHighVisible, isLowVisible) {
            const gd = document.querySelector('.plotly-graph-div');
            const t = this._activeTomographyData;
            if (!t) return [];
            const lons = t.x || t.lons;
            const lats = t.y || t.lats;
            const depths = t.z || t.depths;
            const vpvs = t.vp_vs;
            if (!lons || !depths || lons.length === 0) return [];

            if (neutralRef === undefined || isNaN(neutralRef)) neutralRef = 1.75;
            if (isHighVisible === undefined) isHighVisible = true;
            if (isLowVisible === undefined) isLowVisible = true;

            const uniqueDepths = (t.unique_depths && t.unique_depths.length > 0) 
                ? t.unique_depths 
                : Array.from(new Set(depths.map(d => Math.round(Math.abs(d) * 10) / 10))).sort((a, b) => a - b);
            if (uniqueDepths.length === 0) return [];

            let chosenDepth = 0.8;
            if (targetDepth !== null && targetDepth !== undefined && !isNaN(parseFloat(targetDepth))) {
                chosenDepth = parseFloat(targetDepth);
            } else {
                const inputEl = document.getElementById('tomo-depth-input');
                if (inputEl && inputEl.value !== "") {
                    const parsed = parseFloat(inputEl.value);
                    if (!isNaN(parsed)) chosenDepth = parsed;
                } else if (!uniqueDepths.includes(0.8)) {
                    chosenDepth = uniqueDepths[Math.floor(uniqueDepths.length / 2)];
                }
            }

            let closestDepth = uniqueDepths[0];
            let minDiff = Math.abs(chosenDepth - closestDepth);
            for (const d of uniqueDepths) {
                const diff = Math.abs(chosenDepth - d);
                if (diff < minDiff) {
                    minDiff = diff;
                    closestDepth = d;
                }
            }

            const inputEl = document.getElementById('tomo-depth-input');
            if (inputEl && document.activeElement !== inputEl) {
                inputEl.value = closestDepth.toFixed(1);
            }
            const infoEl = document.getElementById('tomo-slice-info');
            if (infoEl) {
                infoEl.textContent = `Horizontal slice at ${closestDepth.toFixed(1)} km depth`;
            }

            const sliceLons = [];
            const sliceLats = [];
            const sliceVpVs = [];

            let tol = 0.08;
            for (let i = 0; i < depths.length; i++) {
                if (Math.abs(Math.abs(depths[i]) - closestDepth) < tol) {
                    sliceLons.push(lons[i]);
                    sliceLats.push(lats[i]);
                    sliceVpVs.push(vpvs[i]);
                }
            }
            if (sliceLons.length === 0) {
                for (let i = 0; i < depths.length; i++) {
                    if (Math.abs(Math.abs(depths[i]) - closestDepth) < 0.25) {
                        sliceLons.push(lons[i]);
                        sliceLats.push(lats[i]);
                        sliceVpVs.push(vpvs[i]);
                    }
                }
            }
            if (sliceLons.length === 0) return [];

            const N = 40, M = 40;
            let minLat = 999, maxLat = -999, minLon = 999, maxLon = -999;
            for (let i = 0; i < sliceLats.length; i++) {
                if (sliceLats[i] < minLat) minLat = sliceLats[i];
                if (sliceLats[i] > maxLat) maxLat = sliceLats[i];
                if (sliceLons[i] < minLon) minLon = sliceLons[i];
                if (sliceLons[i] > maxLon) maxLon = sliceLons[i];
            }
            minLat -= 0.002; maxLat += 0.002; minLon -= 0.002; maxLon += 0.002;
            const latStep = (maxLat - minLat) / N;
            const lonStep = (maxLon - minLon) / M;

            const cellSums = new Float64Array(N * M);
            const cellCounts = new Int32Array(N * M);

            for (let k = 0; k < sliceLats.length; k++) {
                const row = Math.floor((sliceLats[k] - minLat) / latStep);
                const col = Math.floor((sliceLons[k] - minLon) / lonStep);
                if (row >= 0 && row < N && col >= 0 && col < M) {
                    const idx = row * M + col;
                    cellSums[idx] += sliceVpVs[k];
                    cellCounts[idx]++;
                }
            }

            const featuresHigh = [], locsHigh = [], valsHigh = [], hoverHigh = [];
            const featuresLow = [], locsLow = [], valsLow = [], hoverLow = [];

            for (let r = 0; r < N; r++) {
                const lat1 = minLat + r * latStep;
                const lat2 = lat1 + latStep;
                const clat = (lat1 + lat2) / 2;
                for (let c = 0; c < M; c++) {
                    const idx = r * M + c;
                    if (cellCounts[idx] === 0) continue;
                    const val = cellSums[idx] / cellCounts[idx];
                    const lon1 = minLon + c * lonStep;
                    const lon2 = lon1 + lonStep;
                    const clon = (lon1 + lon2) / 2;
                    const cid = 'tcell_' + idx;
                    const geom = {
                        type: 'Feature',
                        id: cid,
                        properties: { id: cid },
                        geometry: {
                            type: 'Polygon',
                            coordinates: [[[lon1, lat1], [lon2, lat1], [lon2, lat2], [lon1, lat2], [lon1, lat1]]]
                        }
                    };
                    const hTxt = `<b>Tomography Tile Vp/Vs: ${val.toFixed(3)}</b><br>Depth: ${closestDepth.toFixed(1)} km<br>Lat: ${clat.toFixed(4)}°<br>Lon: ${clon.toFixed(4)}°`;
                    if (val >= neutralRef) {
                        featuresHigh.push(geom);
                        locsHigh.push(cid);
                        valsHigh.push(val);
                        hoverHigh.push(hTxt);
                    } else {
                        featuresLow.push(geom);
                        locsLow.push(cid);
                        valsLow.push(val);
                        hoverLow.push(hTxt);
                    }
                }
            }

            const choroType = (gd && gd.layout && gd.layout.map) || (gd && gd.data && gd.data.some(tr => tr.type === 'scattermap' || tr.type === 'choroplethmap')) ? 'choroplethmap' : 'choroplethmapbox';

            const sliceTraces = [];
            if (locsHigh.length > 0) {
                sliceTraces.push({
                    type: choroType,
                    name: `Tomography High Vp/Vs Slice (> ${neutralRef.toFixed(2)})`,
                    geojson: { type: 'FeatureCollection', features: featuresHigh },
                    locations: locsHigh,
                    z: valsHigh,
                    zmin: neutralRef,
                    zmax: 2.35,
                    below: "",
                    hovertext: hoverHigh,
                    hovertemplate: '%{hovertext}<extra></extra>',
                    opacity: 0.75,
                    visible: isHighVisible,
                    colorscale: [
                        [0.0, 'rgb(240, 248, 255)'],
                        [0.5, 'rgb(96, 165, 250)'],
                        [1.0, 'rgb(30, 58, 138)']
                    ],
                    showscale: false,
                    marker: { opacity: 0.75, line: { width: 0.8, color: 'rgba(255, 255, 255, 0.25)' } }
                });
            }
            if (locsLow.length > 0) {
                sliceTraces.push({
                    type: choroType,
                    name: `Tomography Low Vp/Vs Slice (< ${neutralRef.toFixed(2)})`,
                    geojson: { type: 'FeatureCollection', features: featuresLow },
                    locations: locsLow,
                    z: valsLow,
                    zmin: 1.15,
                    zmax: neutralRef,
                    below: "",
                    hovertext: hoverLow,
                    hovertemplate: '%{hovertext}<extra></extra>',
                    opacity: 0.75,
                    visible: isLowVisible,
                    colorscale: [
                        [0.0, 'rgb(220, 38, 38)'],
                        [0.5, 'rgb(249, 115, 22)'],
                        [1.0, 'rgb(254, 240, 138)']
                    ],
                    showscale: false,
                    marker: { opacity: 0.75, line: { width: 0.8, color: 'rgba(255, 255, 255, 0.25)' } }
                });
            }
            return sliceTraces;
        },

        updateTomographySlice(targetDepthStr) {
            if (!this._activeTomographyData) return;
            const gd = document.querySelector('.plotly-graph-div');
            if (!gd || !gd.data) return;
            const isMapboxView = (gd.data && gd.data.some(tr => tr.type === 'scattermapbox' || tr.type === 'densitymapbox' || tr.type === 'scattermap' || tr.type === 'densitymap' || tr.type === 'choroplethmap' || tr.type === 'choroplethmapbox')) || (gd.layout && (gd.layout.mapbox || gd.layout.map));
            if (!isMapboxView) return;
            const t = this._activeTomographyData;
            const lons = t.x || t.lons;
            const depths = t.z || t.depths;
            if (!lons || !depths || lons.length === 0) return;

            const uniqueDepths = (t.unique_depths && t.unique_depths.length > 0) 
                ? t.unique_depths 
                : Array.from(new Set(depths.map(d => Math.round(Math.abs(d) * 100) / 100))).sort((a, b) => a - b);
            if (uniqueDepths.length === 0) return [];

            const minDepth = uniqueDepths[0];
            const maxDepth = uniqueDepths[uniqueDepths.length - 1];

            let targetDepth = parseFloat(targetDepthStr);
            if (isNaN(targetDepth)) {
                const inputEl = document.getElementById('tomo-depth-input');
                if (inputEl && inputEl.value !== "") {
                    targetDepth = parseFloat(inputEl.value);
                }
                if (isNaN(targetDepth)) targetDepth = minDepth;
            }

            if (targetDepth < minDepth) {
                targetDepth = minDepth;
                if (typeof showStatusToast === 'function') showStatusToast(`Depth out of bounds. Showing shallowest slice at ${minDepth} km`, false);
                const inputEl = document.getElementById('tomo-depth-input');
                if (inputEl && document.activeElement !== inputEl) inputEl.value = minDepth;
            } else if (targetDepth > maxDepth) {
                targetDepth = maxDepth;
                if (typeof showStatusToast === 'function') showStatusToast(`Depth out of bounds. Showing deepest slice at ${maxDepth} km`, false);
                const inputEl = document.getElementById('tomo-depth-input');
                if (inputEl && document.activeElement !== inputEl) inputEl.value = maxDepth;
            }

            let closestDepth = uniqueDepths[0];
            let minDiff = Math.abs(targetDepth - closestDepth);
            for (const d of uniqueDepths) {
                const diff = Math.abs(targetDepth - d);
                if (diff < minDiff) {
                    minDiff = diff;
                    closestDepth = d;
                }
            }

            const inputEl = document.getElementById('tomo-depth-input');
            if (inputEl && document.activeElement !== inputEl && parseFloat(inputEl.value) !== closestDepth) {
                inputEl.value = closestDepth;
            }

            const infoEl = document.getElementById('tomo-slice-info');
            if (infoEl) {
                infoEl.textContent = `Showing horizontal slice at ${closestDepth.toFixed(2)} km depth`;
            }

            let isHighVisible = true;
            let isLowVisible = true;
            const btnHigh = document.getElementById('btn-toggle-tomo-high');
            if (btnHigh && btnHigh.innerHTML.includes('OFF')) isHighVisible = false;
            const btnLow = document.getElementById('btn-toggle-tomo-low');
            if (btnLow && btnLow.innerHTML.includes('OFF')) isLowVisible = false;
            const btnMain = document.getElementById('btn-toggle-tomo-points');
            if (btnMain && btnMain.innerHTML.includes('OFF')) {
                isHighVisible = false;
                isLowVisible = false;
            }

            let neutralRef = 1.75;
            const neutralInputEl = document.getElementById('tomo-neutral-input');
            if (neutralInputEl && neutralInputEl.value) {
                const parsedNeut = parseFloat(neutralInputEl.value);
                if (!isNaN(parsedNeut) && parsedNeut >= 1.2 && parsedNeut <= 2.5) {
                    neutralRef = parsedNeut;
                }
            }

            const sliceTraces = this._buildTomographySliceTraces(closestDepth, neutralRef, isHighVisible, isLowVisible);

            const indicesToDelete = [];
            gd.data.forEach((tr, idx) => {
                if (tr.name && (tr.name === 'Tomography Slice Vp/Vs' || tr.name === 'Tomography Vp/Vs' || tr.name.includes('Tomography High Vp/Vs Slice') || tr.name.includes('Tomography Low Vp/Vs Slice') || tr.name === 'Tomography Inspection Points')) {
                    indicesToDelete.push(idx);
                }
            });

            const self = this;
            if (indicesToDelete.length > 0) {
                try {
                    Plotly.deleteTraces(gd, indicesToDelete);
                } catch (delErr) {
                    console.warn('Error deleting old slice traces:', delErr);
                }
            }

            if (sliceTraces.length > 0) {
                return Plotly.addTraces(gd, sliceTraces).then(() => {
                    return Promise.resolve(self.bringMarkersToFront());
                }).then(() => {
                    if (typeof Plotly.Plots.resize === 'function') {
                        Plotly.Plots.resize(gd);
                    }
                }).catch(err => {
                    console.error('Error updating 2D tomography slice traces:', err);
                });
            } else {
                return Promise.resolve(self.bringMarkersToFront());
            }
        },

        updateTomographyNeutral(val) {
            const gd = document.querySelector('.plotly-graph-div');
            if (!gd || !gd.data) return;
            const parsed = parseFloat(val);
            if (isNaN(parsed) || parsed < 1.2 || parsed > 2.5) return;
            
            const isMapboxView = (gd.data && gd.data.some(tr => tr.type === 'scattermapbox' || tr.type === 'densitymapbox' || tr.type === 'choroplethmapbox' || tr.type === 'scattermap' || tr.type === 'densitymap' || tr.type === 'choroplethmap')) || (gd.layout && (gd.layout.mapbox || gd.layout.map));
            if (isMapboxView) {
                this.updateTomographySlice(null);
                return;
            }
            
            const highIdx = gd.data.findIndex(tr => tr.name && tr.name.includes('High Vp/Vs'));
            const lowIdx = gd.data.findIndex(tr => tr.name && tr.name.includes('Low Vp/Vs'));
            
            if (highIdx !== -1) {
                const tr = gd.data[highIdx];
                const newMax = Math.max((tr.isomax || 2.2), parsed + 0.05);
                Plotly.restyle(gd, {
                    name: `Tomography High Vp/Vs (> ${parsed.toFixed(2)})`,
                    isomin: parsed + 0.01,
                    isomax: newMax
                }, [highIdx]);
            }
            if (lowIdx !== -1) {
                const tr = gd.data[lowIdx];
                const newMin = Math.min((tr.isomin || 1.3), parsed - 0.05);
                Plotly.restyle(gd, {
                    name: `Tomography Low Vp/Vs (< ${parsed.toFixed(2)})`,
                    isomin: newMin,
                    isomax: parsed - 0.01
                }, [lowIdx]);
            }
        },

        bringMarkersToFront() {
            const gd = document.querySelector('.plotly-graph-div');
            if (!gd || !gd.data || gd.data.length <= 1) return Promise.resolve();
            const isMapboxView = (gd.data && gd.data.some(tr => tr.type === 'scattermapbox' || tr.type === 'densitymapbox' || tr.type === 'choroplethmapbox' || tr.type === 'scattermap' || tr.type === 'densitymap' || tr.type === 'choroplethmap')) || (gd.layout && (gd.layout.mapbox || gd.layout.map));
            if (isMapboxView) {
                return Promise.resolve();
            }
            const markerIndices = [];
            for (let i = 0; i < gd.data.length; i++) {
                const tr = gd.data[i];
                if (tr && (tr.type === 'scatter3d' || tr.type === 'scatter')) {
                    markerIndices.push(i);
                }
            }
            if (markerIndices.length > 0 && markerIndices.length < gd.data.length && typeof Plotly.moveTraces === 'function') {
                const newIndices = [];
                const startIdx = gd.data.length - markerIndices.length;
                for (let i = 0; i < markerIndices.length; i++) {
                    newIndices.push(startIdx + i);
                }
                const needsMove = markerIndices.some((idx, i) => idx !== newIndices[i]);
                if (needsMove) {
                    try {
                        Plotly.moveTraces(gd, markerIndices, newIndices);
                    } catch (e) {
                        console.warn('Could not move traces to front:', e);
                    }
                }
            }
            return Promise.resolve();
        },

        toggleUpliftSurface() {
            const gd = document.querySelector('.plotly-graph-div');
            if (!gd || !gd.data) return;
            const indices = [];
            for (let i = 0; i < gd.data.length; i++) {
                const n = gd.data[i].name || '';
                if (n === 'Uplift Interpolated Surface' || n === 'Uplift Surface' || n.includes('Colonnine') || n.includes('Superficie Uplift')) {
                    indices.push(i);
                }
            }
            if (indices.length > 0) {
                const isCurrentlyVisible = (gd.data[indices[0]].visible !== false && gd.data[indices[0]].visible !== 'legendonly');
                const newVis = !isCurrentlyVisible;

                const btn = document.getElementById('btn-toggle-uplift-surface');
                if (btn) {
                    btn.innerHTML = newVis ? 'Toggle Uplift (ON)' : 'Toggle Uplift (OFF)';
                    if (newVis) btn.classList.add('active'); else btn.classList.remove('active');
                }

                indices.forEach(idx => {
                    gd.data[idx].visible = newVis;
                });

                Plotly.restyle(gd, { visible: newVis }, indices).catch(err => {
                    console.warn('Plotly restyle uplift warning:', err);
                    try { Plotly.redraw(gd); } catch (e) {}
                });

                if (typeof showStatusToast === 'function') showStatusToast('Uplift toggled ' + (newVis ? 'ON' : 'OFF'), true);
                if (typeof this.updateLegendSwapButtonVisibility === 'function') {
                    this.updateLegendSwapButtonVisibility();
                } else if (window.SeismicUI && typeof window.SeismicUI.updateLegendSwapButtonVisibility === 'function') {
                    window.SeismicUI.updateLegendSwapButtonVisibility();
                }
            } else if (this._activeUpliftData) {
                const isMapbox = (gd.data && gd.data.some(tr => tr.type === 'scattermapbox' || tr.type === 'choroplethmapbox' || tr.type === 'scattermap' || tr.type === 'choroplethmap')) || (gd.layout && (gd.layout.mapbox || gd.layout.map));
                let tracesToAdd = [];
                if (isMapbox) {
                    tracesToAdd = this._buildUplift2DTraces(this._activeUpliftData, true);
                } else {
                    const u = this._activeUpliftData;
                    if (u.interp_grid && u.interp_grid.grid_lons_2d) {
                        tracesToAdd.push({
                            type: 'surface',
                            name: 'Uplift Interpolated Surface',
                            x: u.interp_grid.grid_lons_2d,
                            y: u.interp_grid.grid_lats_2d,
                            z: u.interp_grid.grid_z_2d,
                            surfacecolor: u.interp_grid.grid_up_2d,
                            colorscale: [[0, 'rgb(255, 255, 0)'], [0.5, 'rgb(255, 140, 0)'], [1, 'rgb(139, 0, 0)']],
                            showscale: false,
                            opacity: 0.7,
                            hoverinfo: 'skip',
                            visible: true
                        });
                    }
                }
                if (tracesToAdd.length > 0) {
                    Plotly.addTraces(gd, tracesToAdd).then(() => {
                        const btn = document.getElementById('btn-toggle-uplift-surface');
                        if (btn) {
                            btn.innerHTML = 'Toggle Uplift (ON)';
                            btn.classList.add('visible', 'active');
                        }
                        if (typeof showStatusToast === 'function') showStatusToast('Uplift tiles activated (ON)', true);
                        if (typeof this.updateLegendSwapButtonVisibility === 'function') {
                            this.updateLegendSwapButtonVisibility();
                        } else if (window.SeismicUI && typeof window.SeismicUI.updateLegendSwapButtonVisibility === 'function') {
                            window.SeismicUI.updateLegendSwapButtonVisibility();
                        }
                    }).catch(err => {
                        console.error('Error adding uplift traces:', err);
                    });
                }
            } else {
                if (typeof showStatusToast === 'function') showStatusToast('Select and apply Uplift CSV first', false);
            }
        },

        toggleTomography() {
            const gd = document.querySelector('.plotly-graph-div');
            if (!gd || !gd.data) return;
            const indices = [];
            for (let i = 0; i < gd.data.length; i++) {
                const n = gd.data[i].name || '';
                if (n.includes('Tomography High Vp/Vs') || n.includes('Tomography Low Vp/Vs') || n.includes('Tomography 2D Slice') || n.includes('Tomography') || n.includes('Tomografia') || n.includes('Vp/Vs')) {
                    indices.push(i);
                }
            }
            if (indices.length > 0) {
                const isCurrentlyVisible = (gd.data[indices[0]].visible !== false && gd.data[indices[0]].visible !== 'legendonly');
                const newVis = !isCurrentlyVisible;

                const btn = document.getElementById('btn-toggle-tomo-points');
                if (btn) {
                    btn.innerHTML = newVis ? 'Toggle Tomography (ON)' : 'Toggle Tomography (OFF)';
                    if (newVis) btn.classList.add('active'); else btn.classList.remove('active');
                }
                const btnHigh = document.getElementById('btn-toggle-tomo-high');
                if (btnHigh) {
                    btnHigh.innerHTML = newVis ? 'High (ON)' : 'High (OFF)';
                    if (newVis) btnHigh.classList.add('active'); else btnHigh.classList.remove('active');
                }
                const btnLow = document.getElementById('btn-toggle-tomo-low');
                if (btnLow) {
                    btnLow.innerHTML = newVis ? 'Low (ON)' : 'Low (OFF)';
                    if (newVis) btnLow.classList.add('active'); else btnLow.classList.remove('active');
                }

                indices.forEach(idx => {
                    gd.data[idx].visible = newVis;
                });

                Plotly.restyle(gd, { visible: newVis }, indices).then(() => {
                    const terrainIdx = gd.data.findIndex(tr => tr && (tr.name === 'Map Terrain' || (tr.type === 'surface' && tr.name && tr.name.includes('Terrain'))));
                    if (terrainIdx !== -1) {
                        Plotly.restyle(gd, { opacity: newVis ? 0.35 : 0.9 }, [terrainIdx]);
                    }
                }).catch(err => {
                    console.warn('Plotly restyle tomography warning:', err);
                    try { Plotly.redraw(gd); } catch (e) {}
                });

                if (typeof showStatusToast === 'function') showStatusToast('Tomography toggled ' + (newVis ? 'ON' : 'OFF'), true);
                if (typeof this.updateLegendSwapButtonVisibility === 'function') {
                    this.updateLegendSwapButtonVisibility();
                } else if (window.SeismicUI && typeof window.SeismicUI.updateLegendSwapButtonVisibility === 'function') {
                    window.SeismicUI.updateLegendSwapButtonVisibility();
                }
            } else if (this._activeTomographyData) {
                const traces = this._buildTomographySliceTraces(null, 1.75, true, true);
                if (traces.length > 0) {
                    Plotly.addTraces(gd, traces).then(() => {
                        const btn = document.getElementById('btn-toggle-tomo-points');
                        if (btn) {
                            btn.innerHTML = 'Toggle Tomography (ON)';
                            btn.classList.add('visible', 'active');
                        }
                        const btnHigh = document.getElementById('btn-toggle-tomo-high');
                        if (btnHigh) { btnHigh.innerHTML = 'High (ON)'; btnHigh.classList.add('visible', 'active'); }
                        const btnLow = document.getElementById('btn-toggle-tomo-low');
                        if (btnLow) { btnLow.innerHTML = 'Low (ON)'; btnLow.classList.add('visible', 'active'); }
                        if (typeof showStatusToast === 'function') showStatusToast('Tomography tiles activated (ON)', true);
                        if (typeof this.updateLegendSwapButtonVisibility === 'function') {
                            this.updateLegendSwapButtonVisibility();
                        } else if (window.SeismicUI && typeof window.SeismicUI.updateLegendSwapButtonVisibility === 'function') {
                            window.SeismicUI.updateLegendSwapButtonVisibility();
                        }
                    });
                }
            } else {
                if (typeof showStatusToast === 'function') showStatusToast('Select and apply Tomography CSV first', false);
            }
        },

        toggleTomographyHigh() {
            const gd = document.querySelector('.plotly-graph-div');
            if (!gd || !gd.data) return;
            const indices = [];
            for (let i = 0; i < gd.data.length; i++) {
                if (gd.data[i].name && gd.data[i].name.includes('High Vp/Vs')) {
                    indices.push(i);
                }
            }
            if (indices.length > 0) {
                const isCurrentlyVisible = (gd.data[indices[0]].visible !== false && gd.data[indices[0]].visible !== 'legendonly');
                const newVis = !isCurrentlyVisible;
                
                const btn = document.getElementById('btn-toggle-tomo-high');
                if (btn) {
                    btn.innerHTML = newVis ? 'High (ON)' : 'High (OFF)';
                    if (newVis) btn.classList.add('active'); else btn.classList.remove('active');
                }

                indices.forEach(idx => {
                    gd.data[idx].visible = newVis;
                });

                Plotly.restyle(gd, { visible: newVis }, indices).catch(err => {
                    console.warn('Plotly restyle tomography high warning:', err);
                    try { Plotly.redraw(gd); } catch (e) {}
                });

                if (typeof showStatusToast === 'function') showStatusToast('Tomography High Vp/Vs toggled ' + (newVis ? 'ON' : 'OFF'), true);
            }
        },

        toggleTomographyLow() {
            const gd = document.querySelector('.plotly-graph-div');
            if (!gd || !gd.data) return;
            const indices = [];
            for (let i = 0; i < gd.data.length; i++) {
                if (gd.data[i].name && gd.data[i].name.includes('Low Vp/Vs')) {
                    indices.push(i);
                }
            }
            if (indices.length > 0) {
                const isCurrentlyVisible = (gd.data[indices[0]].visible !== false && gd.data[indices[0]].visible !== 'legendonly');
                const newVis = !isCurrentlyVisible;

                const btn = document.getElementById('btn-toggle-tomo-low');
                if (btn) {
                    btn.innerHTML = newVis ? 'Low (ON)' : 'Low (OFF)';
                    if (newVis) btn.classList.add('active'); else btn.classList.remove('active');
                }

                indices.forEach(idx => {
                    gd.data[idx].visible = newVis;
                });

                Plotly.restyle(gd, { visible: newVis }, indices).catch(err => {
                    console.warn('Plotly restyle tomography low warning:', err);
                    try { Plotly.redraw(gd); } catch (e) {}
                });

                if (typeof showStatusToast === 'function') showStatusToast('Tomography Low Vp/Vs toggled ' + (newVis ? 'ON' : 'OFF'), true);
            }
        },

        toggleStations() {
            const gd = document.querySelector('.plotly-graph-div');
            if (!gd || !gd.data) return;
            const indices = [];
            for (let i = 0; i < gd.data.length; i++) {
                const n = gd.data[i].name || '';
                if (n === 'Stations' || n === 'Stations Outline' || n === 'GNSS Uplift Stations') {
                    indices.push(i);
                }
            }
            if (indices.length > 0) {
                const isCurrentlyVisible = (gd.data[indices[0]].visible !== false && gd.data[indices[0]].visible !== 'legendonly');
                const newVis = !isCurrentlyVisible;
                Plotly.restyle(gd, { visible: newVis }, indices).then(() => {
                    const btn = document.getElementById('btn-toggle-stations');
                    if (btn) {
                        btn.innerHTML = newVis ? 'Toggle Stations (ON)' : 'Toggle Stations (OFF)';
                        if (newVis) btn.classList.add('active'); else btn.classList.remove('active');
                    }
                    if (typeof showStatusToast === 'function') showStatusToast('Stations toggled ' + (newVis ? 'ON' : 'OFF'), true);
                }).catch(err => {
                    console.error('Error restyling stations:', err);
                });
            } else {
                if (typeof showStatusToast === 'function') showStatusToast('No Stations layer loaded to toggle', false);
            }
        },

        swapLegend() {
            const available = (window.SeismicUI && typeof window.SeismicUI.getAvailableLegendScales === 'function')
                ? window.SeismicUI.getAvailableLegendScales()
                : [];

            if (available.length <= 1) {
                return;
            }

            let currentIdx = available.indexOf(window._currentLegendMode);
            if (currentIdx === -1) currentIdx = 0;
            const nextIdx = (currentIdx + 1) % available.length;
            const nextMode = available[nextIdx];
            window._currentLegendMode = nextMode;

            const btn = document.getElementById('btn-swap-legend');
            const container = document.getElementById('legend-container');
            const clusterList = document.getElementById('cluster-list');
            const scaleWrapper = document.getElementById('legend-scale-wrapper');
            const scaleToggle = document.getElementById('legend-scale-toggle');
            const scaleMenu = document.getElementById('legend-scale-menu');

            if (!this._layerScales) {
                this._layerScales = {
                    earthquakes: 'Viridis',
                    vectors: 'Vectors',
                    tomo: 'Tomography',
                    uplift: 'Uplift'
                };
            }

            const bodyWrapper = document.getElementById('legend-body-wrapper');
            if (nextMode === 'clusters') {
                if (bodyWrapper) bodyWrapper.style.display = 'none';
                if (scaleWrapper) scaleWrapper.style.display = 'none';
            } else {
                if (bodyWrapper) bodyWrapper.style.display = 'flex';
                if (scaleWrapper) scaleWrapper.style.display = 'flex';
                const activeScale = this._layerScales[nextMode] || (nextMode === 'vectors' ? 'Vectors' : (nextMode === 'tomo' ? 'Tomography' : (nextMode === 'uplift' ? 'Uplift' : 'Viridis')));
                if (scaleToggle) scaleToggle.title = 'Color scale: ' + activeScale;
                const swatch = document.getElementById('legend-scale-swatch');
                if (swatch) {
                    const colorsMap = window.COLORS_MAP || {};
                    let sColors = colorsMap[activeScale] || colorsMap['Viridis'] || ['#440154', '#fde725'];
                    swatch.style.background = `linear-gradient(to top, ${sColors.join(',')})`;
                }
                if (scaleMenu) {
                    scaleMenu.querySelectorAll('.menu-item').forEach(mi => {
                        if (mi.dataset.val === activeScale) mi.classList.add('active');
                        else mi.classList.remove('active');
                    });
                }
            }

            if (!this._layerInverts) {
                this._layerInverts = { earthquakes: false, vectors: false, tomo: false, uplift: false };
            }
            const currentLayerInvert = !!this._layerInverts[nextMode];
            const invertCheck = document.getElementById('invert-scale');
            if (invertCheck) {
                invertCheck.checked = currentLayerInvert;
            }

            const legend = document.getElementById('glass-legend');
            const updateLegendFn = (typeof updateGlassLegendInternal === 'function') 
                ? updateGlassLegendInternal 
                : (window.updateGlassLegendInternal || function() {});

            if (nextMode === 'earthquakes') {
                if (container) container.style.display = 'flex';
                if (clusterList) clusterList.style.display = 'none';
                if (scaleWrapper) scaleWrapper.style.display = 'flex';
                if (legend) legend.style.paddingBottom = '2.6rem';
                const sc = this._layerScales.earthquakes || (window._earthquakeLegendState ? window._earthquakeLegendState.scaleName : 'Viridis');
                if (window._earthquakeLegendState) {
                    const s = window._earthquakeLegendState;
                    updateLegendFn(s.show, s.title, sc, currentLayerInvert, s.limits, s.dateInfo);
                }
            } else if (nextMode === 'vectors') {
                if (container) container.style.display = 'flex';
                if (clusterList) clusterList.style.display = 'none';
                if (scaleWrapper) scaleWrapper.style.display = 'flex';
                if (legend) legend.style.paddingBottom = '2.6rem';
                const sc = this._layerScales.vectors || 'Vectors';
                let maxV = (window.SeismicUI && window.SeismicUI._consecutiveVectorCount) || this._consecutiveVectorCount;
                if (!maxV || maxV <= 1) {
                    const gd = document.querySelector('.plotly-graph-div');
                    if (gd && gd.data) {
                        const vTr = gd.data.find(tr => tr && tr.name === 'Consecutive Event Vectors');
                        if (vTr && vTr.line && vTr.line.cmax) maxV = vTr.line.cmax;
                    }
                }
                if (!maxV || maxV <= 1) maxV = 100;
                updateLegendFn(true, 'VECTOR N°', sc, currentLayerInvert, [1, maxV], null);
            } else if (nextMode === 'clusters') {
                if (container) container.style.display = 'none';
                if (clusterList) clusterList.style.display = 'flex';
                if (scaleWrapper) scaleWrapper.style.display = 'none';
                if (legend) legend.style.paddingBottom = '2.6rem';
                const titleEl = document.getElementById('legend-title');
                if (titleEl) titleEl.textContent = 'Clusters';
            } else if (nextMode === 'tomo') {
                if (container) container.style.display = 'flex';
                if (clusterList) clusterList.style.display = 'none';
                if (scaleWrapper) scaleWrapper.style.display = 'flex';
                if (legend) legend.style.paddingBottom = '2.6rem';
                const sc = this._layerScales.tomo || 'Tomography';
                const t = this._activeTomographyData;
                let minV = 1.15, maxV = 2.35;
                if (t) {
                    if (t.min_vp_vs !== undefined && t.max_vp_vs !== undefined) {
                        minV = t.min_vp_vs; maxV = t.max_vp_vs;
                    } else if (t.vp_vs && t.vp_vs.length > 0) {
                        minV = Math.min(...t.vp_vs);
                        maxV = Math.max(...t.vp_vs);
                    }
                }
                updateLegendFn(true, 'Tomo Vp/Vs', sc, currentLayerInvert, [minV, maxV], null);
            } else if (nextMode === 'uplift') {
                if (container) container.style.display = 'flex';
                if (clusterList) clusterList.style.display = 'none';
                if (scaleWrapper) scaleWrapper.style.display = 'flex';
                if (legend) legend.style.paddingBottom = '2.6rem';
                const sc = this._layerScales.uplift || 'Uplift';
                const u = this._activeUpliftData;
                let minU = 0, maxU = 0.08;
                if (u) {
                    const vals = u.up_m || u.up_m_list || (u.interp_grid ? u.interp_grid.up_m : []) || [];
                    if (vals.length > 0) {
                        minU = Math.min(...vals);
                        maxU = Math.max(...vals);
                    }
                }
                updateLegendFn(true, 'Uplift (mm)', sc, currentLayerInvert, [minU * 1000, maxU * 1000], null);
            }

            if (typeof this.updateLegendSwapButtonVisibility === 'function') {
                this.updateLegendSwapButtonVisibility();
            } else if (window.SeismicUI && typeof window.SeismicUI.updateLegendSwapButtonVisibility === 'function') {
                window.SeismicUI.updateLegendSwapButtonVisibility();
            }
        },

        handleOverlayUpload(input) {
            try {
                if (!input.files || !input.files[0]) return;
                const file = input.files[0];
                this._pendingMapFile = file;
                const statusEl = document.getElementById('status-layer-map');
                if (statusEl) {
                    statusEl.textContent = file.name;
                    statusEl.style.color = '#10b981';
                }
                const btn = document.getElementById('btn-layer-map');
                if (btn) btn.classList.add('selected');
                input.value = '';
                if (typeof showStatusToast === 'function') showStatusToast(`Map file selected: ${file.name}`, true);
                return;
            } catch (err) {
                console.error('[Overlay] Top-level error:', err);
                if (typeof showStatusToast === 'function') showStatusToast('Error: ' + err.message, false);
                const loader = document.getElementById('loader');
                if (loader) loader.classList.remove('show');
            }
        },

        _applyMapFile(file) {
            try {
                const btn = document.getElementById('overlay-btn');
                const loader = document.getElementById('loader');

                const gd = document.querySelector('.plotly-graph-div');
                if (!gd || !gd.data || !gd.data[0]) {
                    if (typeof showStatusToast === 'function') showStatusToast('No 3D scene found', false);
                    return;
                }

                const traceData = gd._fullData ? gd._fullData[0] : gd.data[0];

                const gridCols = traceData.x ? traceData.x.length : 0;
                const gridRows = traceData.y ? traceData.y.length : 0;

                if (!gridRows || !gridCols) {
                    if (typeof showStatusToast === 'function') showStatusToast('Cannot detect surface dimensions', false);
                    console.error('[Overlay] No x/y dimensions found');
                    return;
                }

                if (!this._originalMapData && traceData.surfacecolor) {
                    try {
                        this._originalMapData = {
                            surfacecolor: JSON.parse(JSON.stringify(traceData.surfacecolor)),
                            colorscale: JSON.parse(JSON.stringify(traceData.colorscale)),
                            cmin: traceData.cmin,
                            cmax: traceData.cmax
                        };
                    } catch (e) {
                        console.error('[Overlay] Failed to save original:', e);
                    }
                }

                const loaderText = loader ? loader.querySelector('.loader-text') : null;
                if (loaderText) loaderText.textContent = 'Applying image overlay…';
                if (loader) loader.classList.add('show');

                const self = this;

                const reader = new FileReader();
                reader.onload = function(e) {
                    const img = new Image();
                    img.onload = function() {
                        setTimeout(function() {
                            try {
                                const canvas = document.createElement('canvas');
                                canvas.width = gridCols;
                                canvas.height = gridRows;
                                const ctx = canvas.getContext('2d');
                                ctx.drawImage(img, 0, 0, gridCols, gridRows);

                                const imageData = ctx.getImageData(0, 0, gridCols, gridRows);
                                const pixels = imageData.data;

                                const matrix = [];
                                const colorCounts = new Map();
                                
                                for (let i = 0; i < pixels.length; i += 4) {
                                    if (pixels[i+3] < 128) continue;
                                    const qr = pixels[i] >> 3;
                                    const qg = pixels[i+1] >> 3;
                                    const qb = pixels[i+2] >> 3;
                                    const key = (qr << 10) | (qg << 5) | qb;
                                    colorCounts.set(key, (colorCounts.get(key) || 0) + 1);
                                }

                                const sortedColors = Array.from(colorCounts.entries())
                                    .sort((a, b) => b[1] - a[1])
                                    .slice(0, 256);
                                
                                const palette = sortedColors.map(([key]) => [
                                    (key >> 10) << 3,
                                    ((key >> 5) & 31) << 3,
                                    (key & 31) << 3
                                ]);
                                
                                if (palette.length < 2) palette.push([0,0,0], [255,255,255]);

                                const maxIdx = palette.length - 1;
                                const colorscale = palette.map((c, i) => [
                                    i / maxIdx, 
                                    `rgb(${c[0]},${c[1]},${c[2]})`
                                ]);

                                for (let row = 0; row < gridRows; row++) {
                                    const matRow = [];
                                    for (let col = 0; col < gridCols; col++) {
                                        const idx = (row * gridCols + col) * 4;
                                        const r = pixels[idx];
                                        const g = pixels[idx + 1];
                                        const b = pixels[idx + 2];
                                        
                                        let bestIdx = 0;
                                        let minDist = Infinity;
                                        for (let i = 0; i < palette.length; i++) {
                                            const d = Math.pow(r - palette[i][0], 2) + 
                                                      Math.pow(g - palette[i][1], 2) + 
                                                      Math.pow(b - palette[i][2], 2);
                                            if (d < minDist) {
                                                minDist = d;
                                                bestIdx = i;
                                            }
                                        }
                                        matRow.push(bestIdx);
                                    }
                                    matrix.push(matRow);
                                }

                                Plotly.restyle(gd, {
                                    surfacecolor: [matrix],
                                    colorscale: [colorscale],
                                    cmin: [0],
                                    cmax: [maxIdx]
                                }, [0]).then(function() {
                                    if (btn) btn.classList.add('active');
                                    self._overlayActive = true;
                                    if (loader) loader.classList.remove('show');
                                    if (typeof showStatusToast === 'function') showStatusToast('Map overlay applied successfully!', true);
                                }).catch(function(err) {
                                    console.error('[Overlay] Restyle failed:', err);
                                    if (loader) loader.classList.remove('show');
                                    if (typeof showStatusToast === 'function') showStatusToast('Failed to apply overlay', false);
                                });
                            } catch (err) {
                                console.error('[Overlay] Processing error:', err);
                                if (loader) loader.classList.remove('show');
                                if (typeof showStatusToast === 'function') showStatusToast('Error: ' + err.message, false);
                            }
                        }, 150);
                    };
                    img.onerror = function() {
                        if (loader) loader.classList.remove('show');
                        if (typeof showStatusToast === 'function') showStatusToast('Failed to load image', false);
                    };
                    img.src = e.target.result;
                };
                reader.onerror = function() {
                    if (loader) loader.classList.remove('show');
                    if (typeof showStatusToast === 'function') showStatusToast('Failed to read file', false);
                };
                reader.readAsDataURL(file);
                const inp = document.getElementById('overlay-input');
                if (inp) inp.value = '';
            } catch (err) {
                console.error('[Overlay] Top-level error:', err);
                if (typeof showStatusToast === 'function') showStatusToast('Error: ' + err.message, false);
                const loader = document.getElementById('loader');
                if (loader) loader.classList.remove('show');
            }
        },

        restoreOriginalMap() {
            if (!this._originalMapData) return;
            const gd = document.querySelector('.plotly-graph-div');
            if (!gd) return;

            const loader = document.getElementById('loader');
            const loaderText = loader ? loader.querySelector('.loader-text') : null;
            if (loaderText) loaderText.textContent = 'Restoring original map…';
            if (loader) loader.classList.add('show');

            const self = this;
            setTimeout(function() {
                Plotly.restyle(gd, {
                    surfacecolor: [self._originalMapData.surfacecolor],
                    colorscale: [self._originalMapData.colorscale],
                    cmin: [self._originalMapData.cmin !== undefined ? self._originalMapData.cmin : null],
                    cmax: [self._originalMapData.cmax !== undefined ? self._originalMapData.cmax : null]
                }, [0]).then(function() {
                    const btn = document.getElementById('overlay-btn');
                    if (btn) btn.classList.remove('active');
                    self._overlayActive = false;
                    if (loader) loader.classList.remove('show');
                    if (typeof showStatusToast === 'function') showStatusToast('Original map restored successfully!', true);
                }).catch(function() {
                    if (loader) loader.classList.remove('show');
                    if (typeof showStatusToast === 'function') showStatusToast('Failed to restore map', false);
                });
            }, 100);
        }
    };

    window.SeismicLayers = SeismicLayers;
    window.SeismicUI = Object.assign(window.SeismicUI || {}, SeismicLayers);
})();
