const DATA_URL = (window.SEISMIC_CONFIG && window.SEISMIC_CONFIG.dataUrl) || '__DATA_URL__';

        async function initCluster() {
            window.IS_CLUSTER_VIEW = true;
            window.quakeData = await fetchAndUnpackSeismicData(DATA_URL);


            const gd = document.querySelector('.plotly-graph-div');
            const startInput = document.getElementById('filter-start');
            const endInput = document.getElementById('filter-end');
            const magMin = document.getElementById('mag-min');
            const magMax = document.getElementById('mag-max');
            const depMin = document.getElementById('dep-min');
            const depMax = document.getElementById('dep-max');

            const methodToggle = document.getElementById('method-toggle');
            const methodMenu = document.getElementById('method-menu');
            const displayToggle = document.getElementById('display-toggle');
            const displayMenu = document.getElementById('display-menu');
            const sizeToggle = document.getElementById('size-toggle');
            const sizeMenu = document.getElementById('size-menu');
            let currentSizeMode = 'uniform';

            function getArrayMinMax(arr) {
                let min = Infinity, max = -Infinity;
                for (let i = 0, len = arr.length; i < len; i++) {
                    const v = arr[i];
                    if (v < min) min = v;
                    if (v > max) max = v;
                }
                return [min, max];
            }

            const [magMinVal, magMaxVal] = getArrayMinMax(quakeData.magnitude);
            magMin.value = magMinVal.toFixed(1);
            magMax.value = magMaxVal.toFixed(1);

            if (quakeData.dep_range && quakeData.dep_range.length >= 2) {
                depMin.value = 0;
                depMax.value = Math.ceil(Math.max(Math.abs(quakeData.dep_range[0]), Math.abs(quakeData.dep_range[1])));
            } else {
                let maxD = 0;
                for (let i = 0; i < quakeData.depth.length; i++) {
                    const d = Math.abs(quakeData.depth[i]);
                    if (d > maxD) maxD = d;
                }
                depMin.value = 0;
                depMax.value = Math.ceil(maxD);
            }

            let currentDisplayMode = 'wireframe';
            let currentMethod = quakeData.clustering_method || 'dbscan';

            // Recover previous display mode if set in params
            if (quakeData.clustering_params && quakeData.clustering_params.display_mode) {
                currentDisplayMode = quakeData.clustering_params.display_mode;
            }

            // Snapshot baseline auto-tune parameters from backend
            const initialAutoTuneParams = JSON.parse(JSON.stringify(quakeData.clustering_params || {}));
            const initialMethod = currentMethod;

            // Parameter Inputs

            const kmParams = document.getElementById('kmeans-params');
            const dbParams = document.getElementById('dbscan-params');
            const hdbParams = document.getElementById('hdbscan-params');
            const pClusters = document.getElementById('param-clusters');
            const pDist = document.getElementById('param-dist');
            const pEps = document.getElementById('param-eps');
            const pMin = document.getElementById('param-min-samples');
            const pHdbMinCluster = document.getElementById('param-hdb-min-cluster');
            const pHdbMinSamples = document.getElementById('param-hdb-min-samples');
            const pHdbEps = document.getElementById('param-hdb-eps');
            const pUseTime = document.getElementById('param-use-time');
            const pTimeWindow = document.getElementById('param-time-window');
            const spatiotemporalParams = document.getElementById('spatiotemporal-params');
            const btnAutotuneTime = document.getElementById('btn-autotune-time');

            // Initialize params from backend if they exist
            if (quakeData.clustering_params) {
                const cp = quakeData.clustering_params;
                if (cp.kmeans_clusters) pClusters.value = cp.kmeans_clusters;
                if (cp.kmeans_max_dist) pDist.value = cp.kmeans_max_dist;
                if (cp.dbscan_eps) pEps.value = cp.dbscan_eps;
                if (cp.dbscan_min_samples) pMin.value = cp.dbscan_min_samples;
                if (cp.hdbscan_min_cluster_size && pHdbMinCluster) pHdbMinCluster.value = cp.hdbscan_min_cluster_size;
                if (cp.hdbscan_min_samples && pHdbMinSamples) pHdbMinSamples.value = cp.hdbscan_min_samples;
                if (cp.hdbscan_cluster_selection_epsilon !== undefined && pHdbEps) pHdbEps.value = cp.hdbscan_cluster_selection_epsilon;
                else if (cp.hdbscan_eps !== undefined && pHdbEps) pHdbEps.value = cp.hdbscan_eps;
                if (cp.use_time !== undefined && pUseTime) {
                    pUseTime.checked = Boolean(cp.use_time);
                    if (spatiotemporalParams) spatiotemporalParams.style.display = pUseTime.checked ? 'block' : 'none';
                }
                if (cp.time_window_hours && pTimeWindow) {
                    pTimeWindow.value = cp.time_window_hours;
                } else if (cp.time_window && pTimeWindow) {
                    pTimeWindow.value = cp.time_window;
                } else if (cp.time_window_days && pTimeWindow) {
                    pTimeWindow.value = Math.round(cp.time_window_days * 24 * 10) / 10;
                }
                
                // Restore Filters
                if (cp.mag_min) magMin.value = cp.mag_min;
                if (cp.mag_max) magMax.value = cp.mag_max;
                if (cp.dep_min) depMin.value = cp.dep_min;
                if (cp.dep_max) depMax.value = cp.dep_max;
                if (cp.start_date) startInput.value = cp.start_date;
                if (cp.end_date) endInput.value = cp.end_date;
                if (cp.show_cluster_planes) document.getElementById('show-planes').checked = cp.show_cluster_planes;
            }

            if (pUseTime && spatiotemporalParams) {
                pUseTime.onchange = () => {
                    spatiotemporalParams.style.display = pUseTime.checked ? 'block' : 'none';
                };
            }

            if (btnAutotuneTime) {
                btnAutotuneTime.onclick = async (e) => {
                    e.preventDefault();
                    try {
                        let res = null;
                        if (window.seismicSocket) {
                            res = await window.seismicSocket.sendRequest('auto_tune_time_window', {});
                        } else if (window.pywebview && window.pywebview.api && window.pywebview.api.auto_tune_time_window) {
                            res = await window.pywebview.api.auto_tune_time_window();
                        }
                        if (res) {
                            const hours = res.time_window_hours || (res.time_window_days ? Math.round(res.time_window_days * 24 * 10) / 10 : 72);
                            if (pTimeWindow) pTimeWindow.value = hours;
                            applyCombinedFilters();
                        }
                    } catch(err) {
                        console.warn("Autotune time window error:", err);
                    }
                };
            }


            function syncParamVisibility() {
                kmParams.style.display = currentMethod === 'kmeans' ? 'block' : 'none';
                dbParams.style.display = currentMethod === 'dbscan' ? 'block' : 'none';
                if (hdbParams) hdbParams.style.display = currentMethod === 'hdbscan' ? 'block' : 'none';
            }

            // Set initial method toggle text
            const methodLabelMap = { 'dbscan': 'DBSCAN', 'hdbscan': 'HDBSCAN', 'kmeans': 'K-Means' };
            methodToggle.textContent = (methodLabelMap[currentMethod] || 'DBSCAN') + ' ▾';
            methodMenu.querySelectorAll('.menu-item').forEach(i => {
                i.classList.toggle('active', i.dataset.val === currentMethod);
            });
            syncParamVisibility();

            // Menus
            SeismicUI.initMenu(methodToggle, methodMenu);
            SeismicUI.initMenu(displayToggle, displayMenu);
            SeismicUI.initMenu(sizeToggle, sizeMenu);

            SeismicUI.bindMenu(sizeMenu, (item) => {
                currentSizeMode = item.dataset.mode;
                sizeToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
            });

            SeismicUI.bindMenu(methodMenu, (item) => {
                currentMethod = item.dataset.val;
                methodToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
                syncParamVisibility();
            });

            SeismicUI.bindMenu(displayMenu, (item) => {
                currentDisplayMode = item.dataset.mode;
                displayToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
                // Defer update: no call to applyDisplayMode() here
            });


            // Range input sanitization (Passive)
            SeismicUI.setupBoundsValidation(magMin, magMin.value, null);
            SeismicUI.setupBoundsValidation(magMax, magMax.value, null);
            SeismicUI.setupBoundsValidation(depMin, depMin.value, null);
            SeismicUI.setupBoundsValidation(depMax, depMax.value, null);


            const applyBtn = document.getElementById('apply-filters-btn');




            function applyCombinedFilters() {
                const params = {
                    kmeans_clusters: pClusters.value,
                    kmeans_max_dist: pDist.value,
                    dbscan_eps: pEps.value,
                    dbscan_min_samples: pMin.value,
                    hdbscan_min_cluster_size: pHdbMinCluster ? pHdbMinCluster.value : 5,
                    hdbscan_min_samples: pHdbMinSamples ? pHdbMinSamples.value : 3,
                    hdbscan_cluster_selection_epsilon: pHdbEps ? pHdbEps.value : 0,
                    hdbscan_eps: pHdbEps ? pHdbEps.value : 0,
                    use_time: pUseTime ? pUseTime.checked : false,
                    time_window_hours: pTimeWindow ? (parseFloat(pTimeWindow.value) || 72.0) : 72.0,
                    time_window: pTimeWindow ? (parseFloat(pTimeWindow.value) || 72.0) : 72.0,
                    time_window_days: pTimeWindow ? ((parseFloat(pTimeWindow.value) || 72.0) / 24.0) : 3.0,
                    display_mode: currentDisplayMode,
                    show_cluster_planes: document.getElementById('show-planes').checked,
                    point_size_mode: currentSizeMode,
                    mag_min: magMin ? magMin.value : 0,
                    mag_max: magMax ? magMax.value : 10,
                    dep_min: depMin ? depMin.value : 0,
                    dep_max: depMax ? depMax.value : 1000,
                    start_date: startInput ? startInput.value : '',
                    end_date: endInput ? endInput.value : ''
                };

                if (quakeData.subcluster_target_indices) {
                    params.subcluster_target_indices = quakeData.subcluster_target_indices;
                }
                if (quakeData.subcluster_context_indices) {
                    params.subcluster_context_indices = quakeData.subcluster_context_indices;
                }
                if (window.lockedClusters && window.lockedClusters.size > 0 && quakeData && quakeData.n_clusters) {
                    const lockedMap = {};
                    for (let i = 0; i < quakeData.n_clusters; i++) {
                        if (window.lockedClusters.has(i)) {
                            let indices = [];
                            if (quakeData.cluster_indices && quakeData.cluster_indices[i]) {
                                indices = quakeData.cluster_indices[i];
                            } else if (quakeData.cluster) {
                                for (let p = 0; p < quakeData.cluster.length; p++) {
                                    if (quakeData.cluster[p] === i) indices.push(p);
                                }
                            }
                            if (indices.length > 0) lockedMap[i] = indices;
                        }
                    }
                    if (Object.keys(lockedMap).length > 0) {
                        params.locked_clusters = lockedMap;
                    }
                }

                if(typeof showInitLoader === 'function') showInitLoader('Applying clustering...');

                setTimeout(async () => {
                    if (window.seismicSocket) {
                        try {
                            const res = await window.seismicSocket.sendRequest('get_cluster_update', {
                                method: currentMethod,
                                params: params
                            });
                            if (res && res.traces) {
                                // Delete all traces except Surface (index 0)
                                const currentTraceCount = gd.data.length;
                                if (currentTraceCount > 1) {
                                    const indices = Array.from({length: currentTraceCount - 1}, (_, i) => i + 1);
                                    Plotly.deleteTraces(gd, indices);
                                }
                                // Add new ones
                                Plotly.addTraces(gd, res.traces);
                                
                                // Update local state for legend
                                quakeData.n_clusters = res.n_clusters;
                                if (res.method) quakeData.clustering_method = res.method;
                                else quakeData.clustering_method = currentMethod;
                                if (res.params) quakeData.clustering_params = res.params;
                                else quakeData.clustering_params = params;
                                if (res.cluster_indices) quakeData.cluster_indices = res.cluster_indices;
                                if (res.labels) {
                                    if (quakeData.subcluster_target_indices) {
                                        const targets = quakeData.subcluster_target_indices;
                                        if (targets.length === res.labels.length) {
                                            for (let i = 0; i < targets.length; i++) {
                                                quakeData.cluster[targets[i]] = res.labels[i];
                                            }
                                        }
                                    } else {
                                        quakeData.cluster = res.labels;
                                    }
                                }

                                const eqTr = res.traces.find(t => t.name === 'Earthquakes');
                                if (eqTr && eqTr.x) {
                                    window.currentFilteredData = {
                                        longitude: eqTr.x,
                                        latitude: eqTr.y,
                                        depth: eqTr.z
                                    };
                                    if (window.quakeData) window.quakeData.filtered = window.currentFilteredData;
                                }

                                // Sync legend and display mode
                                applyDisplayMode();
                                updateClusterLegend();
                                const evCheck = document.getElementById('event-vectors-check');
                                if (window.SeismicUI) {
                                    if (evCheck && evCheck.checked) {
                                        window.SeismicUI.toggleConsecutiveArrows(true);
                                    } else if (window.SeismicUI._activeConsecutiveArrows) {
                                        window.SeismicUI.toggleConsecutiveArrows(false);
                                    }
                                }
                            } else if (res && res.error) {
                                console.error("Update Error:", res.error);
                                if (typeof showStatusToast === 'function') showStatusToast(res.error, false);
                            }
                        } catch (err) {
                            console.error("Async Error:", err);
                        }
                    } else {
                        // Fallback for dev
                        applyDisplayMode();
                    }
                    if(typeof hideInitLoader === 'function') hideInitLoader();
                }, 100);
            }




            applyBtn.onclick = applyCombinedFilters;

            [startInput, endInput, magMin, magMax, depMin, depMax].forEach(input => {
                if (input) {
                    input.addEventListener('change', applyCombinedFilters);
                    input.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter') applyCombinedFilters();
                    });
                }
            });

            if (pTimeWindow) {
                pTimeWindow.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') applyCombinedFilters();
                });
            }

            const dates = (quakeData.times && Array.isArray(quakeData.times)) ? quakeData.times.map(t => t.slice(0, 10)) : [];
            const uniqueDates = Array.from(new Set(dates)).sort();
            if (uniqueDates.length > 0) {
                startInput.min = endInput.min = uniqueDates[0];
                startInput.max = endInput.max = uniqueDates[uniqueDates.length - 1];
                if (!startInput.value) startInput.value = uniqueDates[0];
                if (!endInput.value) endInput.value = uniqueDates[uniqueDates.length - 1];
            }

            const [depMinVal, depMaxVal] = getArrayMinMax(quakeData.depth.map(Math.abs));
            depMin.value = 0;
            depMax.value = Math.ceil(depMaxVal);

            const resetBtn = document.getElementById('reset-filters-btn');
            if (resetBtn) {
                resetBtn.onclick = (e) => {
                    e.preventDefault();
                    const cp = initialAutoTuneParams;
                    
                    // 1. Restore clustering method
                    if (cp.clustering_method && methodLabelMap[cp.clustering_method]) {
                        currentMethod = cp.clustering_method;
                        methodToggle.textContent = (methodLabelMap[currentMethod] || 'DBSCAN') + ' ▾';
                        methodMenu.querySelectorAll('.menu-item').forEach(i => {
                            i.classList.toggle('active', i.dataset.val === currentMethod);
                        });
                        syncParamVisibility();
                    }

                    // 2. Restore auto-tuned clustering parameters
                    pClusters.value = cp.kmeans_clusters || 3;
                    pDist.value = cp.kmeans_max_dist !== undefined ? cp.kmeans_max_dist : 0;
                    pEps.value = cp.dbscan_eps || 500;
                    pMin.value = cp.dbscan_min_samples || 5;
                    if (pHdbMinCluster) pHdbMinCluster.value = cp.hdbscan_min_cluster_size || 5;
                    if (pHdbMinSamples) pHdbMinSamples.value = cp.hdbscan_min_samples || 3;
                    if (pHdbEps) pHdbEps.value = cp.hdbscan_cluster_selection_epsilon !== undefined ? cp.hdbscan_cluster_selection_epsilon : (cp.hdbscan_eps || 0);

                    if (pUseTime) {
                        pUseTime.checked = Boolean(cp.use_time);
                        if (spatiotemporalParams) spatiotemporalParams.style.display = pUseTime.checked ? 'block' : 'none';
                    }
                    if (pTimeWindow) {
                        pTimeWindow.value = cp.time_window_hours || cp.time_window || (cp.time_window_days ? Math.round(cp.time_window_days * 24 * 10) / 10 : 72);
                    }

                    // 3. Reset filters (magnitude, depth, dates) to full dataset bounds
                    if (magMin) magMin.value = '';
                    if (magMax) magMax.value = '';
                    if (depMin) depMin.value = 0;
                    if (depMax) depMax.value = Math.ceil(depMaxVal);
                    if (uniqueDates.length > 0) {
                        startInput.value = uniqueDates[0];
                        endInput.value = uniqueDates[uniqueDates.length - 1];
                    }

                    const showPlanesEl = document.getElementById('show-planes');
                    if (showPlanesEl) {
                        showPlanesEl.checked = Boolean(cp.show_cluster_planes);
                    }

                    if (typeof showStatusToast === 'function') {
                        showStatusToast("Parameters reset to auto-tuned defaults", true);
                    }

                    applyCombinedFilters();
                };
            }

            /**
             * applyDisplayMode()
             * Locally toggles the visibility of Wireframe/Solid traces based on the dropdown.
             * Optimized with a single restyle call.
             */
            function applyDisplayMode() {
                const showWire = (currentDisplayMode === 'wireframe' || currentDisplayMode === 'both');
                const showSolid = (currentDisplayMode === 'solid' || currentDisplayMode === 'both');
                const showPlanes = document.getElementById('show-planes').checked;
                const showContextPointsCheck = document.getElementById('show-context-points');
                const showContextPoints = showContextPointsCheck ? showContextPointsCheck.checked : true;

                const update = { visible: [] };
                const indices = [];

                for (let i = 0; i < gd.data.length; i++) {
                    const name = gd.data[i].name || '';
                    if (name.endsWith(' Wire')) {
                        indices.push(i);
                        update.visible.push(showWire);
                    } else if (name.endsWith(' Solid')) {
                        indices.push(i);
                        update.visible.push(showSolid);
                    } else if (name.endsWith(' Plane')) {
                        indices.push(i);
                        update.visible.push(showPlanes);
                    } else if (name === 'Other Events') {
                        indices.push(i);
                        update.visible.push(showContextPoints);
                    }
                }

                if (indices.length > 0) {
                    Plotly.restyle(gd, update, indices);
                }
            }

            const isSubcluster = new URLSearchParams(window.location.search).get('subcluster') === 'true';
            if (isSubcluster) {
                const contextGroup = document.getElementById('context-points-group');
                if (contextGroup) contextGroup.style.display = 'block';
            }
            
            window.applyAllSubclusters = async function() {
                if(typeof showInitLoader === 'function') showInitLoader('Applying subclusters to main view...');
                try {
                    const clusterArr = Array.from(quakeData.cluster);
                    await pywebview.api.apply_subclusters(clusterArr);
                } catch(e) {
                    console.error("Failed to apply subclusters:", e);
                    if (typeof showStatusToast === 'function') showStatusToast('Engine failure: ' + e);
                    if(typeof hideInitLoader === 'function') hideInitLoader();
                }
            };


            // Initialize locked clusters state from backend
            window.lockedClusters = new Set((quakeData && quakeData.locked_cluster_ids) ? quakeData.locked_cluster_ids : []);

            window.toggleClusterLock = function(internalLbl) {
                if (window.lockedClusters.has(internalLbl)) {
                    window.lockedClusters.delete(internalLbl);
                } else {
                    window.lockedClusters.add(internalLbl);
                }
                updateClusterLegend();
            };

            window.lockAllClusters = function() {
                for (let i = 0; i < quakeData.n_clusters; i++) {
                    window.lockedClusters.add(i);
                }
                updateClusterLegend();
            };

            window.unlockAllClusters = function() {
                window.lockedClusters.clear();
                updateClusterLegend();
            };

            window.subclusterUnlocked = async function() {
                let targetIndices = [];
                let lockedClustersMap = {};

                for (let i = 0; i < quakeData.n_clusters; i++) {
                    let indices = [];
                    if (quakeData.cluster_indices && quakeData.cluster_indices[i]) {
                        indices = quakeData.cluster_indices[i];
                    } else if (quakeData.cluster) {
                        for (let p = 0; p < quakeData.cluster.length; p++) {
                            if (quakeData.cluster[p] === i) {
                                indices.push(p);
                            }
                        }
                    }

                    if (window.lockedClusters.has(i)) {
                        lockedClustersMap[i] = indices;
                    } else {
                        targetIndices.push(...indices);
                    }
                }

                if (targetIndices.length === 0) {
                    console.warn("All clusters are locked or no points available.");
                    if (typeof showStatusToast === 'function') showStatusToast('No unlocked clusters available to subdivide.');
                    return;
                }

                if(typeof showInitLoader === 'function') showInitLoader('Loading subcluster view...');

                try {
                    let contextIndices = null;
                    if (quakeData.subcluster_context_indices) {
                        contextIndices = quakeData.subcluster_context_indices;
                    }

                    const method = quakeData.clustering_method || 'dbscan';
                    const params = quakeData.clustering_params || {};
                    if (typeof window.updateHistoryState === 'function') await window.updateHistoryState();
                    await pywebview.api.load_subcluster_view(targetIndices, contextIndices, method, params, lockedClustersMap);
                } catch(e) {
                    console.error("Failed to load subcluster view:", e);
                    if (typeof showStatusToast === 'function') showStatusToast('Engine failure: ' + e);
                    if(typeof hideInitLoader === 'function') hideInitLoader();
                }
            };

            // Build custom glass legend for clusters
            function updateClusterLegend() {
                const clusterList = document.getElementById('cluster-list');
                const legend = document.getElementById('glass-legend');
                const swapBtn = document.getElementById('btn-swap-legend');
                if (!clusterList) return;
                
                if (legend) {
                    legend.style.display = 'flex';
                    legend.style.width = '10.5rem';
                    legend.style.minWidth = '10.5rem';
                    legend.style.maxWidth = '10.5rem';
                    legend.style.height = '31vh';
                    legend.style.minHeight = '13.5rem';
                    legend.style.maxHeight = '20rem';
                    const hasSwap = swapBtn && swapBtn.style.display !== 'none';
                    legend.style.padding = hasSwap ? '0.85rem 0.65rem 2.6rem 0.65rem' : '0.85rem 0.65rem 0.85rem 0.65rem';
                }

                const savedScrollTop = clusterList.scrollTop || 0;
                
                let html = '';

                if (quakeData.n_clusters > 0) {
                    html += `
                        <div style="display:flex; gap:0.35rem; width:100%; margin-bottom:0.35rem; flex-shrink:0;">
                            <button class="btn-cluster-action btn-cluster-lock" onclick="lockAllClusters()" title="Blocca tutti i cluster">Lock All</button>
                            <button class="btn-cluster-action btn-cluster-unlock" onclick="unlockAllClusters()" title="Sblocca tutti i cluster">Unlock All</button>
                        </div>
                        <div style="margin-bottom:0.45rem; width:100%; flex-shrink:0;">
                            <button class="btn-cluster-subcluster" onclick="subclusterUnlocked()" title="Perform subclustering on unlocked clusters">Subclustering</button>
                        </div>
                    `;
                }

                for (let i = 0; i < quakeData.n_clusters; i++) {
                    const internalLbl = i;
                    const displayNum = i + 1;
                    const color = getClusterColor(i);
                    const isLocked = window.lockedClusters.has(internalLbl);
                    const lockBtnStyle = isLocked
                        ? "background:rgba(245,158,11,0.25); border:1px solid rgba(245,158,11,0.6); color:#fcd34d;"
                        : "background:rgba(255,255,255,0.1); border:1px solid rgba(255,255,255,0.2); color:#fff;";
                    const lockText = isLocked ? "Locked" : "Unlocked";

                    html += `
                        <div class="legend-item-cluster" style="display:flex; align-items:center; justify-content:space-between; gap:0.5rem; flex-shrink:0; width:100%; margin-bottom: 0.35rem;">
                            <span style="font-family:inherit;font-size:0.75rem;font-weight:600;color:#fff;opacity:0.9;">Cluster ${displayNum}</span>
                            <div style="display:flex; align-items:center; gap:0.35rem;">
                                <button class="btn-cluster-item-lock" onclick="toggleClusterLock(${internalLbl})" style="${lockBtnStyle}" title="Toggle lock state">${lockText}</button>
                                <div style="width:0.875rem;height:0.875rem;border-radius:50%;background-color:${color};border:1px solid rgba(255,255,255,0.4);box-shadow:0 0 0.375rem ${color}80;"></div>
                            </div>
                        </div>
                    `;
                }
                
                clusterList.innerHTML = html;

                if (!window._currentLegendMode || window._currentLegendMode === 'clusters' || window._currentLegendMode === 'earthquakes') {
                    window._currentLegendMode = 'clusters';
                    clusterList.style.display = 'flex';
                    const container = document.getElementById('legend-container');
                    if (container) container.style.display = 'none';
                    const scaleWrapper = document.getElementById('legend-scale-wrapper');
                    if (scaleWrapper) scaleWrapper.style.display = 'none';
                    const bodyWrapper = document.getElementById('legend-body-wrapper');
                    if (bodyWrapper) bodyWrapper.style.display = 'none';
                    document.getElementById('legend-title').textContent = 'Clusters';
                }

                if (window.SeismicUI && typeof window.SeismicUI.updateSwapLegendVisibility === 'function') {
                    window.SeismicUI.updateSwapLegendVisibility();
                }

                if (savedScrollTop > 0) {
                    clusterList.scrollTop = savedScrollTop;
                }
            }

            window.analyzeCluster = async function(internalLbl) {
                let indices = [];
                if (quakeData.cluster_indices && quakeData.cluster_indices[internalLbl]) {
                    indices = quakeData.cluster_indices[internalLbl];
                } else if (quakeData.cluster) {
                    for (let i = 0; i < quakeData.cluster.length; i++) {
                        if (quakeData.cluster[i] === internalLbl) {
                            indices.push(i);
                        }
                    }
                }
                
                if (indices.length === 0) {
                    console.error("No points found for cluster " + internalLbl);
                    return;
                }

                if(typeof showInitLoader === 'function') showInitLoader('Loading subcluster view...');

                try {
                    let contextIndices = null;
                    if (quakeData.subcluster_context_indices) {
                        contextIndices = quakeData.subcluster_context_indices;
                    }
                    
                    const method = quakeData.clustering_method || 'dbscan';
                    const params = quakeData.clustering_params || {};
                    await pywebview.api.load_subcluster_view(indices, contextIndices, method, params);
                } catch(e) {
                    console.error("Failed to load subcluster view:", e);
                    if (typeof showStatusToast === 'function') showStatusToast('Engine failure: ' + e);
                    if(typeof hideInitLoader === 'function') hideInitLoader();
                }
            };

            // --- INITIAL RENDER ---
            
            // Set initial selection in menu if it was passed from backend
            displayMenu.querySelectorAll('.menu-item').forEach(item => {
                if (item.dataset.mode === currentDisplayMode) {
                    displayMenu.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    displayToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
                }
            });

            // Initial view is already rendered by backend, just sync legend
            window.updateHistoryState = async function() {
                if (window.pywebview && window.pywebview.api && typeof quakeData !== 'undefined') {
                    const method = quakeData.clustering_method || 'dbscan';
                    const params = quakeData.clustering_params || {};
                    const lockedMap = {};
                    if (window.lockedClusters) {
                        for (const [k, v] of window.lockedClusters.entries()) {
                            lockedMap[k] = Array.from(v);
                        }
                    }
                    await pywebview.api.update_history_state(method, params, Object.keys(lockedMap).length > 0 ? lockedMap : null);
                }
            };
            
            window.getCurrentFrameClusterExportData = function() {
                if (!quakeData) return null;
                const clustersList = [];
                const nC = quakeData.n_clusters || 0;
                
                for (let i = 0; i < nC; i++) {
                    let indices = [];
                    if (quakeData.cluster_indices && (quakeData.cluster_indices[i] !== undefined || quakeData.cluster_indices[String(i)] !== undefined)) {
                        indices = quakeData.cluster_indices[i] || quakeData.cluster_indices[String(i)] || [];
                    } else if (quakeData.cluster) {
                        for (let p = 0; p < quakeData.cluster.length; p++) {
                            if (quakeData.cluster[p] === i) indices.push(p);
                        }
                    }
                    if (indices && indices.length > 0) {
                        const cNum = i + 1;
                        clustersList.push({
                            name: `Cluster ${cNum}`,
                            filename: `cluster_${cNum}.csv`,
                            clusterNum: cNum,
                            internalLbl: i,
                            indices: indices
                        });
                    }
                }

                let outlierIndices = [];
                if (quakeData.cluster_indices && (quakeData.cluster_indices[-1] !== undefined || quakeData.cluster_indices['-1'] !== undefined)) {
                    outlierIndices = quakeData.cluster_indices[-1] || quakeData.cluster_indices['-1'] || [];
                } else if (quakeData.cluster) {
                    for (let p = 0; p < quakeData.cluster.length; p++) {
                        if (quakeData.cluster[p] === -1) outlierIndices.push(p);
                    }
                }
                if (outlierIndices && outlierIndices.length > 0) {
                    clustersList.push({
                        name: "Outliers",
                        filename: "outliers.csv",
                        clusterNum: -1,
                        internalLbl: -1,
                        indices: outlierIndices
                    });
                }

                if (clustersList.length === 0) return null;

                return {
                    method: quakeData.clustering_method || 'dbscan',
                    params: quakeData.clustering_params || {},
                    clusters: clustersList
                };
            };

            applyDisplayMode();
            updateClusterLegend();

            const evCheckInit = document.getElementById('event-vectors-check');
            if (evCheckInit && !evCheckInit._hooked) {
                evCheckInit._hooked = true;
                evCheckInit.addEventListener('change', () => {
                    if (window.SeismicUI && typeof window.SeismicUI.toggleConsecutiveArrows === 'function') {
                        window.SeismicUI.toggleConsecutiveArrows(evCheckInit.checked);
                    }
                });
            }

            // Finally hide the loader once everything is ready
            hideInitLoader();
        }

        window.addEventListener('load', function() {
            initCluster().catch(err => {
                console.error('Failed to load cluster data:', err);
                if (typeof showStatusToast === 'function') showStatusToast('Failed to load data.');
                hideInitLoader();
            });
        });
