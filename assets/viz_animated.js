const DATA_URL = (window.SEISMIC_CONFIG && window.SEISMIC_CONFIG.dataUrl) || '__DATA_URL__';
        window.quakeData = null;

        function formatClusterDisplayLabel(lbl, uniqueLabelsList = []) {
            if (lbl >= 100) {
                const cyl = Math.floor(lbl / 1000) || Math.floor(lbl / 100);
                const rem = lbl % 1000;
                const dep = Math.floor(rem / 100);
                const grp = rem % 100;
                if (lbl >= 1000) return `Cyl ${cyl} - D${dep} - Gr ${grp}`;
                return `Cyl ${Math.floor(lbl / 100)} - Gr ${lbl % 100}`;
            }
            const index = Array.isArray(uniqueLabelsList) ? uniqueLabelsList.indexOf(lbl) : -1;
            return index >= 0 ? `Cluster ${index + 1}` : (lbl >= 0 ? `Cluster ${lbl + 1}` : `Cluster ?`);
        }

        async function initAnimation() {
            const quakeData = await fetchAndUnpackSeismicData(DATA_URL);
            window.quakeData = quakeData;
            quakeData.lon = quakeData.longitude;
            quakeData.lat = quakeData.latitude;
            quakeData.mag = quakeData.magnitude;
            quakeData.dep = quakeData.depth;
            quakeData.dnum = quakeData.dates_num;

            if (!quakeData.hover || quakeData.hover.length !== quakeData.lon.length) {
                const qLon = quakeData.lon;
                const qLat = quakeData.lat;
                const qMag = quakeData.mag;
                const qDep = quakeData.dep;
                const qTimes = quakeData.times;
                const N = qLon.length;
                const hArr = new Array(N);
                for (let i = 0; i < N; i++) {
                    const d = (qTimes && qTimes[i]) ? qTimes[i] : '';
                    const m = (qMag && qMag[i] !== undefined) ? Number(qMag[i]).toFixed(1) : '';
                    const dp = (qDep && qDep[i] !== undefined) ? Math.abs(Number(qDep[i])).toFixed(1) : '';
                    const la = (qLat && qLat[i] !== undefined) ? Number(qLat[i]).toFixed(4) : '';
                    const lo = (qLon && qLon[i] !== undefined) ? Number(qLon[i]).toFixed(4) : '';
                    hArr[i] = `Date: ${d}<br>Magnitude: ${m}<br>Latitude: ${la}<br>Longitude: ${lo}<br>Depth: ${dp} km`;
                }
                quakeData.hover = hArr;
            }


            const gd = document.querySelector('.plotly-graph-div');
            if (window.setupPassThroughTerrainHover) window.setupPassThroughTerrainHover(gd);
            const playBtn = document.getElementById('play-btn');
            const pauseBtn = document.getElementById('pause-btn');
            const slider = document.getElementById('time-slider');
            const dateDisplay = document.getElementById('current-date');
            const speedToggle = document.getElementById('speed-toggle');
            const speedMenu = document.getElementById('speed-menu');
            const colorToggle = document.getElementById('color-toggle');
            const colorMenu = document.getElementById('color-menu');
            const sizeToggle = document.getElementById('size-toggle');
            const sizeMenu = document.getElementById('size-menu');
            let currentSizeMode = 'uniform';
            const jumpBtn = document.getElementById('jump-btn');
            const jumpDate = document.getElementById('jump-date');
            const histogramMap = document.getElementById('histogram-map');
            
            const showPlanesCheck = document.getElementById('show-planes');
            const planeControls = document.getElementById('plane-controls');
            const planeRadius = document.getElementById('plane-radius');
            const planeMinPts = document.getElementById('plane-min-pts');
            const accumulatePlanesCheck = document.getElementById('accumulate-planes');


            let isPlaying = false;
            let currentStepIdx = 0;
            let currentMode = 'mag'; 
            let currentColorScale = 'Viridis';
            let invertScale = false;
            
            let planesEnabled = false;
            let accumulatePlanes = false;
            let structuralPlanes = null; // Mapping date -> planes, loaded on demand via WebSocket
            let persistentPlanesMap = new Map(); // grid_id -> plane_data (for accumulation)
            let lastAccumIdx = -1;

            // Clustering state
            let animClusteringEnabled = false;
            let animClustersMap = null; // Mapping date -> {labels: [], planes: []}
            let currentAnimClustMethod = 'dbscan';
            let showAnimClusterPlanes = false;
            
            let speedMult = 1;
            
            let startIdx = 0;
            let animId = null;

            const dates = quakeData.frame_dates || quakeData.unique_dates || [];

            function updateCurrentDateDisplay(idx) {
                if (!dateDisplay || !dates || dates.length === 0) return;
                const date = dates[idx];
                if (!date) return;

                if (quakeData.anim_mode === 'window' && quakeData.window_days > 1) {
                    const cutoffDate = new Date(new Date(date).getTime() - (quakeData.window_days - 1) * 86400000);
                    const cutoffStr = cutoffDate.toISOString().slice(0, 10);
                    dateDisplay.textContent = `${formatDate(cutoffStr)} – ${formatDate(date)}`;
                } else if (quakeData.anim_mode === 'block' && quakeData.window_days > 1) {
                    const blockStartDate = new Date(date);
                    const blockEndDate = new Date(blockStartDate.getTime() + quakeData.window_days * 86400000);
                    const endStr = blockEndDate.toISOString().slice(0, 10);
                    dateDisplay.textContent = `${formatDate(date)} – ${formatDate(endStr)}`;
                } else {
                    dateDisplay.textContent = formatDate(date);
                }
            }

            slider.max = dates.length - 1;
            if (jumpDate) {
                if (dates.length > 0) {
                    jumpDate.min = dates[0];
                    jumpDate.max = dates[dates.length - 1];
                    jumpDate.value = dates[0];
                }
                const handleJump = () => {
                    const target = jumpDate.value ? jumpDate.value.trim() : '';
                    if (!target) return;
                    const idx = dates.findIndex(d => d >= target);
                    if (idx !== -1) {
                        pause();
                        updateView(idx);
                    } else {
                        pause();
                        updateView(dates.length - 1);
                    }
                };
                jumpDate.addEventListener('change', handleJump);
                jumpDate.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') handleJump();
                });
                if (jumpBtn) {
                    jumpBtn.onclick = handleJump;
                }
            }

            let appliedMagMin = -10;
            let appliedMagMax = 10;
            let appliedDepMin = -100;
            let appliedDepMax = 1000;

            const depMinInput = document.getElementById('anim-dep-min');
            const depMaxInput = document.getElementById('anim-dep-max');
            if (depMinInput && depMaxInput) {
                let maxAbsDepth = 0;
                for (let i = 0; i < quakeData.dep.length; i++) {
                    const d = Math.abs(quakeData.dep[i]);
                    if (d > maxAbsDepth) maxAbsDepth = d;
                }
                depMinInput.value = 0;
                depMaxInput.value = Math.ceil(maxAbsDepth);
                appliedDepMin = 0;
                appliedDepMax = Math.ceil(maxAbsDepth);
            }
            const magMinInput = document.getElementById('anim-mag-min');
            const magMaxInput = document.getElementById('anim-mag-max');
            if (magMinInput && magMaxInput) {
                if (quakeData.mag_range && quakeData.mag_range.length >= 2) {
                    magMinInput.value = quakeData.mag_range[0].toFixed(1);
                    magMaxInput.value = quakeData.mag_range[1].toFixed(1);
                } else if (quakeData.mag && quakeData.mag.length > 0) {
                    let minM = Infinity, maxM = -Infinity;
                    for (let i = 0; i < quakeData.mag.length; i++) {
                        const m = quakeData.mag[i];
                        if (m < minM) minM = m;
                        if (m > maxM) maxM = m;
                    }
                    magMinInput.value = (minM !== Infinity ? minM : 0).toFixed(1);
                    magMaxInput.value = (maxM !== -Infinity ? maxM : 10).toFixed(1);
                }
                const mV1 = parseFloat(magMinInput.value);
                const mV2 = parseFloat(magMaxInput.value);
                if (!isNaN(mV1)) appliedMagMin = mV1;
                if (!isNaN(mV2)) appliedMagMax = mV2;
            }
            window.appliedMagMin = appliedMagMin;
            window.appliedMagMax = appliedMagMax;
            window.appliedDepMin = appliedDepMin;
            window.appliedDepMax = appliedDepMax;

            if (SeismicUI && SeismicUI.setupBoundsValidation) {
                SeismicUI.setupBoundsValidation(magMinInput, magMinInput?.value || -10, null);
                SeismicUI.setupBoundsValidation(magMaxInput, magMaxInput?.value || 10, null);
                SeismicUI.setupBoundsValidation(depMinInput, depMinInput?.value || -100, null);
                SeismicUI.setupBoundsValidation(depMaxInput, depMaxInput?.value || 1000, null);
            }

            function formatDate(isoStr) {
                if (!isoStr) return '';
                const parts = isoStr.split('-');
                if (parts.length !== 3) return isoStr;
                return `${parts[1]}/${parts[2]}/${parts[0]}`;
            }

            function fromMMDDYYYY(mmddStr) {
                if (!mmddStr) return '';
                const parts = mmddStr.split(/[/-]/);
                if (parts.length !== 3) return mmddStr;
                const m = parts[0].padStart(2, '0');
                const d = parts[1].padStart(2, '0');
                const y = parts[2];
                return `${y}-${m}-${d}`;
            }

            function getActiveRange(idx) {
                const date = dates[idx];
                let endIdx = quakeData.date_to_cum[date];
                let startIdx = 0;

                if (quakeData.anim_mode === 'window') {
                    const cutoffDate = new Date(new Date(date).getTime() - (quakeData.window_days - 1) * 86400000);
                    const cutoffStr = cutoffDate.toISOString().slice(0, 10);
                    
                    let low = 0, high = dates.length - 1;
                    let foundIdx = 0;
                    while (low <= high) {
                        let mid = (low + high) >>> 1;
                        if (dates[mid] >= cutoffStr) {
                            foundIdx = mid;
                            high = mid - 1;
                        } else {
                            low = mid + 1;
                        }
                    }
                    if (foundIdx > 0) startIdx = quakeData.date_to_cum[dates[foundIdx - 1]];
                } else if (quakeData.anim_mode === 'block') {
                    const startStr = date;
                    const blockStartDate = new Date(startStr);
                    const blockEndDate = new Date(blockStartDate.getTime() + quakeData.window_days * 86400000);
                    const endStr = blockEndDate.toISOString().slice(0, 10);

                    const allDates = quakeData.unique_dates;
                    let low = 0, high = allDates.length - 1;
                    let foundStartIdx = -1;
                    while (low <= high) {
                        let mid = (low + high) >>> 1;
                        if (allDates[mid] < startStr) {
                            foundStartIdx = mid;
                            low = mid + 1;
                        } else {
                            high = mid - 1;
                        }
                    }
                    if (foundStartIdx === -1) startIdx = 0;
                    else startIdx = quakeData.date_to_cum[allDates[foundStartIdx]];

                    let foundEndIdx = -1;
                    low = 0; high = allDates.length - 1;
                    while (low <= high) {
                        let mid = (low + high) >>> 1;
                        if (allDates[mid] < endStr) {
                            foundEndIdx = mid;
                            low = mid + 1;
                        } else {
                            high = mid - 1;
                        }
                    }
                    if (foundEndIdx === -1) endIdx = 0;
                    else endIdx = quakeData.date_to_cum[allDates[foundEndIdx]];
                }
                return [startIdx, endIdx];
            }

            let isRendering = false;
            let pendingUpdateIdx = null;

            async function updateView(idx) {
                const totalFrames = dates.length;
                if (idx < 0) idx = 0;
                if (totalFrames > 0 && idx >= totalFrames) idx = totalFrames - 1;

                if (isRendering) {
                    pendingUpdateIdx = idx;
                    return Promise.resolve();
                }
                isRendering = true;
                try {
                    await _doUpdateView(idx);
                } finally {
                    isRendering = false;
                    if (pendingUpdateIdx !== null && !isPlaying) {
                        const nextIdx = pendingUpdateIdx;
                        pendingUpdateIdx = null;
                        requestAnimationFrame(() => updateView(nextIdx));
                    }
                }
            }

            async function _doUpdateView(idx) {
                const totalFrames = dates.length;
                if (idx < 0) idx = 0;
                if (totalFrames > 0 && idx >= totalFrames) idx = totalFrames - 1;
                
                const range = getActiveRange(idx);
                const start = range[0];
                const end = range[1];

                const magMin = appliedMagMin;
                const magMax = appliedMagMax;
                const depMin = appliedDepMin;
                const depMax = appliedDepMax;
                window.appliedMagMin = appliedMagMin;
                window.appliedMagMax = appliedMagMax;
                window.appliedDepMin = appliedDepMin;
                window.appliedDepMax = appliedDepMax;

                // Fallback for missing hover data (stripped for optimization)
                if (!quakeData.hover || quakeData.hover.length === 0) {
                    quakeData.hover = new Array(quakeData.lon.length).fill("");
                }
                
                // --- 1. Fetch Cluster Data ---
                let clusterData = null;
                if (animClusteringEnabled && animClustersMap && dates[idx]) {
                    clusterData = animClustersMap[dates[idx]];
                }

                let sliceLon, sliceLat, sliceDep, sliceMag, sliceDnum, sliceHover;
                let filteredLabels = [];
                let sliceEventIdx = [];
                let sliceDatasetIndices = [];

                const defaultMag = quakeData.mag_range || quakeData.mag_limit || [-10, 10];
                const defaultDep = quakeData.dep_range || quakeData.dep_limit || [0, 999];
                const isFastPath = !animClusteringEnabled &&
                    magMin <= defaultMag[0] && magMax >= defaultMag[1] &&
                    depMin <= 0 && depMax >= Math.ceil(Math.max(Math.abs(defaultDep[0]), Math.abs(defaultDep[1])));

                if (isFastPath) {
                    sliceLon = quakeData.lon.subarray ? quakeData.lon.subarray(start, end) : quakeData.lon.slice(start, end);
                    sliceLat = quakeData.lat.subarray ? quakeData.lat.subarray(start, end) : quakeData.lat.slice(start, end);
                    sliceDep = quakeData.dep.subarray ? quakeData.dep.subarray(start, end) : quakeData.dep.slice(start, end);
                    sliceMag = quakeData.mag.subarray ? quakeData.mag.subarray(start, end) : quakeData.mag.slice(start, end);
                    sliceDnum = quakeData.dnum.subarray ? quakeData.dnum.subarray(start, end) : quakeData.dnum.slice(start, end);
                    sliceHover = quakeData.hover ? quakeData.hover.slice(start, end) : [];
                } else {
                    sliceLon = [];
                    sliceLat = [];
                    sliceDep = [];
                    sliceMag = [];
                    sliceDnum = [];
                    sliceHover = [];

                    const startD = new Date(quakeData.start_date || '2000-01-01');
                    const startTimestamp = startD.getTime();
                    if (!window._animDateCache) window._animDateCache = new Map();
                    const animDateCache = window._animDateCache;

                    const totalActive = (end - start);
                    for (let k = 0; k < totalActive; k++) {
                        const i = (start + k);
                        const sLocal = k;
                        const m = quakeData.mag[i];
                        const d = quakeData.dep[i];
                        const absD = Math.abs(d);
                        if (m >= magMin && m <= magMax && absD >= depMin && absD <= depMax) {
                            sliceLon.push(quakeData.lon[i]);
                            sliceLat.push(quakeData.lat[i]);
                            sliceDep.push(d);
                            sliceMag.push(m);
                            sliceDnum.push(quakeData.dnum[i]);
                            sliceEventIdx.push(sLocal);
                            sliceDatasetIndices.push(i);

                            let hText = (quakeData.hover && quakeData.hover[i]) ? quakeData.hover[i] : "";
                            if (!hText) {
                                const dayInt = Math.round(quakeData.dnum[i]);
                                let dStr = animDateCache.get(dayInt);
                                if (!dStr) {
                                    const dt = new Date(startTimestamp + dayInt * 86400000);
                                    dStr = `${String(dt.getMonth() + 1).padStart(2, '0')}/${String(dt.getDate()).padStart(2, '0')}/${dt.getFullYear()}`;
                                    animDateCache.set(dayInt, dStr);
                                }
                                hText = `Date: ${dStr}<br>Mag: ${m.toFixed(1)}<br>Dep: ${absD.toFixed(1)} km`;
                                if (quakeData.hover) quakeData.hover[i] = hText;
                            }

                            let lbl = -1;
                            if (clusterData && clusterData.labels) {
                                lbl = clusterData.labels[k];
                            }
                            filteredLabels.push(lbl);
                            sliceHover.push(hText);
                        }
                    }
                }

                // --- 2. Fetch Planes to Render ---
                let planesToRender = [];
                const needsHulls = (typeof currentAnimDisplayMode !== 'undefined') && (currentAnimDisplayMode !== 'points');
                if (animClusteringEnabled && (showAnimClusterPlanes || needsHulls) && clusterData) {
                    planesToRender = clusterData.planes || [];
                    if (accumulatePlanes) {
                        persistentPlanesMap.clear();
                        for (let i = 0; i <= idx; i++) {
                            const daily = (animClustersMap[dates[i]] || {}).planes || [];
                            daily.forEach(p => persistentPlanesMap.set(p.grid_id, p));
                        }
                        planesToRender = Array.from(persistentPlanesMap.values());
                    } else {
                        if (quakeData.anim_mode !== 'block') {
                            if ((!planesToRender || planesToRender.length === 0) && idx > 0) {
                                for (let i = idx - 1; i >= 0; i--) {
                                    const pastPlanes = (animClustersMap[dates[i]] || {}).planes;
                                    if (pastPlanes && pastPlanes.length > 0) {
                                        planesToRender = pastPlanes;
                                        break;
                                    }
                                }
                            }
                        }
                    }
                }

                // --- 3. Compute Global Unique Labels ---
                const visibleLabelsSet = new Set();
                filteredLabels.forEach(l => {
                    if (l !== -1 && l !== undefined && l !== null) visibleLabelsSet.add(l);
                });
                planesToRender.forEach(p => {
                    if (p.grid_id.startsWith('cluster_')) {
                        const rawId = parseInt(p.grid_id.split('_')[1]);
                        if (!isNaN(rawId)) visibleLabelsSet.add(rawId);
                    }
                });
                const globalUniqueLabels = [...visibleLabelsSet].sort((a, b) => a - b);

                // --- 3b. Cache current frame clusters export data ---
                const frameClusters = [];
                if (animClusteringEnabled && clusterData) {
                    globalUniqueLabels.forEach((lbl, index) => {
                        const cIndices = [];
                        for (let j = 0; j < filteredLabels.length; j++) {
                            if (filteredLabels[j] === lbl) {
                                cIndices.push(sliceDatasetIndices[j]);
                            }
                        }
                        if (cIndices.length > 0) {
                            const cNum = index + 1;
                            frameClusters.push({
                                name: `Cluster ${cNum}`,
                                filename: `cluster_${cNum}.csv`,
                                clusterNum: cNum,
                                internalLbl: lbl,
                                indices: cIndices
                            });
                        }
                    });

                    const outlierIndices = [];
                    for (let j = 0; j < filteredLabels.length; j++) {
                        if (filteredLabels[j] === -1) {
                            outlierIndices.push(sliceDatasetIndices[j]);
                        }
                    }
                    if (outlierIndices.length > 0) {
                        frameClusters.push({
                            name: 'Outliers',
                            filename: 'outliers.csv',
                            clusterNum: -1,
                            internalLbl: -1,
                            indices: outlierIndices
                        });
                    }
                }

                window._currentFrameClusterExportData = {
                    method: currentAnimClustMethod || 'dbscan',
                    params: (animClustersMap && animClustersMap.params) || (quakeData && quakeData.clustering_params) || {},
                    clusters: frameClusters
                };

                // --- 4. Populate Hover Text ---
                if (filteredLabels.length > 0) {
                    for (let j = 0; j < sliceHover.length; j++) {
                        const lbl = filteredLabels[j];
                        if (lbl >= 0) {
                            sliceHover[j] += `<br><b>${formatClusterDisplayLabel(lbl, globalUniqueLabels)}</b>`;
                        }
                    }
                }

                let sliceColor, visibleTraceIdx, limits, barTitle;
                const isDate = (currentMode === 'date');
                if (currentMode === 'mag') {
                    sliceColor = sliceMag;
                    visibleTraceIdx = 1;
                    limits = quakeData.mag_range || quakeData.mag_limit;
                    barTitle = 'Magnitude';
                } else if (isDate) {
                    sliceColor = sliceDnum;
                    visibleTraceIdx = 2;
                    limits = quakeData.date_range || quakeData.date_limit;
                    barTitle = 'Date';
                } else {
                    sliceColor = sliceDep;
                    visibleTraceIdx = 3;
                    limits = quakeData.dep_range || quakeData.dep_limit;
                    barTitle = 'Depth (KM)';
                }

                const pScale = (typeof window.getPlotlyScale === 'function' ? window.getPlotlyScale(currentColorScale) : (typeof getPlotlyScale === 'function' ? getPlotlyScale(currentColorScale) : 'Viridis'));
                const markerSizes = currentSizeMode === 'magnitude' ? sliceMag.map(m => Math.max(8, Math.pow(Math.max(0, m), 2) * 1.5)) : 5;

                // --- Optimized Multi-Trace Update ---
                const bulkUpdate = {
                    x: [sliceLon], 
                    y: [sliceLat], 
                    z: [sliceDep],
                    'marker.size': [markerSizes],
                    'marker.color': [sliceColor],
                    'marker.colorscale': [pScale],
                    'marker.reversescale': [invertScale],
                    'marker.cmin': [limits[0]],
                    'marker.cmax': [limits[1]],
                    'marker.showscale': [false],
                    'marker.opacity': [0.85],
                    hovertext: [sliceHover],
                    visible: [true]
                };
                const traceIndices = [visibleTraceIdx];

                if (gd.data[visibleTraceIdx] && gd.data[visibleTraceIdx].marker) {
                    gd.data[visibleTraceIdx].marker.colorscale = pScale;
                    gd.data[visibleTraceIdx].marker.reversescale = invertScale;
                }
                for (let t = 1; t <= 3; t++) {
                    if (t !== visibleTraceIdx && gd.data[t] && gd.data[t].visible !== false) {
                        gd.data[t].visible = false;
                        try { Plotly.restyle(gd, { visible: false }, [t]); } catch (e) {}
                    }
                }

                if (animClusteringEnabled && filteredLabels.length > 0) {
                    const labels = filteredLabels;
                    const currentCount = sliceLon.length;
                    const colorArr = new Array(currentCount).fill('#888888');
                    for (let i = 0; i < Math.min(currentCount, labels.length); i++) {
                        colorArr[i] = getClusterColor(labels[i]);
                    }
                    bulkUpdate['marker.color'] = [colorArr];
                    bulkUpdate['marker.colorscale'] = [null];
                    bulkUpdate['marker.cmin'] = [null];
                    bulkUpdate['marker.cmax'] = [null];
                }
                // --- Mesh Trace Update (Traces 4+) ---
                // Each plane gets its own mesh3d trace for independent hover detection.
                let planeTraces = [];

                if (animClusteringEnabled && clusterData) {
                    if (showAnimClusterPlanes) {
                        planeTraces.push(...generatePlaneTraces(planesToRender, globalUniqueLabels));
                    }
                    if (typeof currentAnimDisplayMode !== 'undefined' && currentAnimDisplayMode !== 'points') {
                        planeTraces.push(...generateHullTraces(planesToRender, currentAnimDisplayMode));
                    }
                } else if (planesEnabled && structuralPlanes) {
                    let planesToDraw = [];
                    if (accumulatePlanes) {
                        persistentPlanesMap.clear();
                        for (let i = 0; i <= idx; i++) {
                            const daily = structuralPlanes[dates[i]] || [];
                            daily.forEach(p => persistentPlanesMap.set(p.grid_id, p));
                        }
                        planesToDraw = Array.from(persistentPlanesMap.values());
                    } else {
                        planesToDraw = structuralPlanes[dates[idx]] || [];
                        if (quakeData.anim_mode !== 'block') {
                            if (planesToDraw.length === 0 && idx > 0) {
                                for (let i = idx - 1; i >= 0; i--) {
                                    const pastPlanes = structuralPlanes[dates[i]];
                                    if (pastPlanes && pastPlanes.length > 0) {
                                        planesToDraw = pastPlanes;
                                        break;
                                    }
                                }
                            }
                        }
                    }
                    planeTraces = generatePlaneTraces(planesToDraw, []);
                }

                currentStepIdx = idx;
                slider.value = currentStepIdx;
                updateCurrentDateDisplay(idx);
                if (jumpDate && dates && dates[idx] && document.activeElement !== jumpDate) {
                    jumpDate.value = dates[idx];
                }

                // 1. Update scatter3d trace (points)
                return Plotly.restyle(gd, bulkUpdate, traceIndices).then(() => {
                    // 2. Mesh traces (from index 4 onwards)
                    if (planeTraces.length === 0) {
                        // No planes: delete extra plane traces
                        const indicesToDelete = [];
                        for (let t = gd.data.length - 1; t >= 4; t--) {
                            const tr = gd.data[t];
                            if (tr) {
                                if (t > 4) {
                                    indicesToDelete.push(t);
                                } else if (t === 4 && tr.visible !== false) {
                                    Plotly.restyle(gd, { visible: false, x: [[]], y: [[]], z: [[]], i: [[]], j: [[]], k: [[]] }, [4]);
                                }
                            }
                        }
                        if (indicesToDelete.length > 0) {
                            Plotly.deleteTraces(gd, indicesToDelete);
                        }
                    } else if (planeTraces.length === 1 && gd.data.length === 5 && gd.data[4].type === 'mesh3d') {
                        // Single plane and placeholder exists: update in place without delete/add
                        const pt = planeTraces[0];
                        Plotly.restyle(gd, {
                            x: [pt.x], y: [pt.y], z: [pt.z],
                            i: [pt.i], j: [pt.j], k: [pt.k],
                            color: [pt.color], opacity: [pt.opacity],
                            hovertext: [pt.hovertext], name: [pt.name],
                            visible: true
                        }, [4]);
                    } else {
                        // Multiple planes or count mismatch: delete extra plane traces and re-add
                        const indicesToDelete = [];
                        for (let t = gd.data.length - 1; t >= 4; t--) {
                            if (gd.data[t]) {
                                indicesToDelete.push(t);
                            }
                        }
                        if (indicesToDelete.length > 0) {
                            Plotly.deleteTraces(gd, indicesToDelete);
                        }
                        Plotly.addTraces(gd, planeTraces);
                    }

                    const dayEnd = quakeData.date_to_cum[dates[idx]];
                        const dayStart = (idx > 0) ? quakeData.date_to_cum[dates[idx-1]] : 0;
                        updateHUD(start, end, dayStart, dayEnd);
                    }).catch(err => {
                    // Ensure legend is still rendered even if restyle caught an error
                    updateGlassLegend(
                        true,
                        barTitle,
                        currentColorScale,
                        invertScale,
                        limits,
                        { startDate: quakeData.start_date }
                    );
                });
            }

            function renderHistogram() {
                const counts = quakeData.date_counts;
                if (!counts || counts.length === 0) return;
                
                // Safety: if too many dates, hide histogram to avoid UI overflow
                if (counts.length > 400) {
                    histogramMap.style.display = 'none';
                    return;
                }
                histogramMap.style.display = 'flex';

                // Adjust gap if many bars
                if (counts.length > 200) {
                    histogramMap.style.gap = '0';
                } else {
                    histogramMap.style.gap = '0.1rem';
                }

                let maxCount = 1;
                for (let c = 0; c < counts.length; c++) {
                    if (counts[c] > maxCount) maxCount = counts[c];
                }
                histogramMap.innerHTML = '';
                
                counts.forEach((count, i) => {
                    const bar = document.createElement('div');
                    bar.className = 'hist-bar';
                    const h = Math.max(2, (count / maxCount) * 100);
                    bar.style.height = `${h}%`;
                    bar.title = `${dates[i]}: ${count} events`;
                    
                    bar.onclick = (e) => {
                        e.stopPropagation();
                        pause();
                        updateView(i);
                    };
                    
                    histogramMap.appendChild(bar);
                });
            }

            function updateHUD(windowStart, windowEnd, frameStart, frameEnd) {
                const count = Math.max(0, windowEnd - windowStart);
                if (count === 0) {
                    document.getElementById('stat-count').textContent = '0';
                    document.getElementById('stat-max-mag').textContent = '0.0';
                    document.getElementById('stat-avg-dep').textContent = '0.0 km';
                    document.getElementById('stat-energy').textContent = '0.0';
                    return;
                }

                let maxMag = -Infinity;
                let sumDep = 0;
                const mags = quakeData.mag;
                const deps = quakeData.dep;
                for (let j = windowStart; j < windowEnd; j++) {
                    const mVal = mags[j];
                    if (mVal > maxMag) maxMag = mVal;
                    sumDep += Math.abs(deps[j]);
                }
                const avgDep = count > 0 ? (sumDep / count) : 0;
                if (maxMag === -Infinity) maxMag = 0;

                let totalEnergy = 0;
                for (let k = frameStart; k < frameEnd; k++) {
                    totalEnergy += Math.pow(10, 1.8 + 1.5 * mags[k]);
                }

                let energyStr = totalEnergy.toExponential(1);
                if (totalEnergy < 1e6) energyStr = Math.round(totalEnergy).toLocaleString();

                document.getElementById('stat-count').textContent = count.toLocaleString();
                document.getElementById('stat-max-mag').textContent = maxMag.toFixed(1);
                document.getElementById('stat-avg-dep').textContent = `${Math.abs(avgDep).toFixed(1)} km`;
                document.getElementById('stat-energy').textContent = energyStr + ' kJ';
            }

            function updateHUDArrays(sliceMagWindow, sliceDepWindow, sliceMagFrame) {
                
                const count = sliceMagWindow.length;
                if (count === 0) {
                    document.getElementById('stat-count').textContent = '0';
                    document.getElementById('stat-max-mag').textContent = '0.0';
                    document.getElementById('stat-avg-dep').textContent = '0.0 km';
                    document.getElementById('stat-energy').textContent = '0.0';
                    return;
                }
                
                let maxMag = -Infinity;
                let sumDep = 0;
                for (let j = 0; j < count; j++) {
                    const mVal = sliceMagWindow[j];
                    if (mVal > maxMag) maxMag = mVal;
                    sumDep += Math.abs(sliceDepWindow[j]);
                }
                const avgDep = count > 0 ? (sumDep / count) : 0;
                if (maxMag === -Infinity) maxMag = 0;
                
                // Energy Release (kJ) using Gutenberg-Richter relation: log10(E) = 4.8 + 1.5 * M
                // We divide by 1000 for kJ, so the constant becomes 4.8 - 3 = 1.8
                let totalEnergy = 0;
                for (let m of sliceMagFrame) {
                    totalEnergy += Math.pow(10, 1.8 + 1.5 * m);
                }
                
                let energyStr = totalEnergy.toExponential(1);
                if (totalEnergy < 1e6) energyStr = Math.round(totalEnergy).toLocaleString();
                
                document.getElementById('stat-count').textContent = count.toLocaleString();
                document.getElementById('stat-max-mag').textContent = maxMag.toFixed(1);
                document.getElementById('stat-avg-dep').textContent = `${Math.abs(avgDep).toFixed(1)} km`;
                document.getElementById('stat-energy').textContent = energyStr + ' kJ';
            }

            function getHexFromScale(scaleName, val01) {
                let colors = COLORS_MAP[scaleName] || COLORS_MAP['Viridis'];
                if (invertScale) val01 = 1 - val01;
                const idx = Math.round(val01 * (colors.length - 1));
                return colors[Math.min(colors.length - 1, Math.max(0, idx))];
            }

            window.lockedClustersAnim = window.lockedClustersAnim || new Set();

            window.toggleClusterLockAnim = function(lbl) {
                if (window.lockedClustersAnim.has(lbl)) {
                    window.lockedClustersAnim.delete(lbl);
                } else {
                    window.lockedClustersAnim.add(lbl);
                }
                updateClusterLegend(window._lastPresentLabels || []);
            };

            window.lockAllClustersAnim = function() {
                const labels = window._lastPresentLabels || [];
                labels.forEach(lbl => {
                    if (lbl !== -1 && lbl !== undefined && lbl !== null) {
                        window.lockedClustersAnim.add(lbl);
                    }
                });
                updateClusterLegend(window._lastPresentLabels || []);
            };

            window.unlockAllClustersAnim = function() {
                window.lockedClustersAnim.clear();
                updateClusterLegend(window._lastPresentLabels || []);
            };

            window.subclusterUnlockedAnim = async function() {
                let targetIndices = [];
                let contextIndices = [];
                let lockedClustersMap = {};

                if (animClustersMap && typeof currentStepIdx !== 'undefined') {
                    const dateStr = dates[currentStepIdx];
                    const frameData = animClustersMap[dateStr];
                    if (frameData && frameData.labels && frameData.indices) {
                        contextIndices = frameData.indices;
                        for (let i = 0; i < frameData.labels.length; i++) {
                            const lbl = frameData.labels[i];
                            const ptIdx = frameData.indices[i];
                            if (window.lockedClustersAnim.has(lbl)) {
                                if (!lockedClustersMap[lbl]) lockedClustersMap[lbl] = [];
                                lockedClustersMap[lbl].push(ptIdx);
                            } else {
                                targetIndices.push(ptIdx);
                            }
                        }
                    }
                }

                if (targetIndices.length === 0) {
                    console.warn("All clusters are locked or no points available in current frame.");
                    if (typeof showStatusToast === 'function') showStatusToast('No unlocked clusters available to subdivide.');
                    return;
                }

                if(typeof showInitLoader === 'function') showInitLoader('Loading subcluster view...');

                try {
                    const params = {
                        kmeans_clusters: pClustersAnim.value,
                        kmeans_max_dist: pDistAnim.value,
                        dbscan_eps: pEpsAnim.value,
                        dbscan_min_samples: pMinAnim.value
                    };
                    await pywebview.api.load_subcluster_view(targetIndices, contextIndices, currentAnimClustMethod, params, lockedClustersMap);
                } catch(e) {
                    console.error("Failed to load subcluster view:", e);
                    if (typeof showStatusToast === 'function') showStatusToast('Engine failure: ' + e);
                    if(typeof hideInitLoader === 'function') hideInitLoader();
                }
            };

            function updateClusterLegend(presentLabels) {
                const clusterList = document.getElementById('cluster-list');
                const legend = document.getElementById('glass-legend');
                const swapBtn = document.getElementById('btn-swap-legend');
                const scaleWrapper = document.getElementById('legend-scale-wrapper');
                const invertGroup = document.getElementById('legend-invert-group');
                if (!clusterList) return;
                if (legend) {
                    legend.style.width = '10.5rem';
                    legend.style.minWidth = '10.5rem';
                    legend.style.maxWidth = '10.5rem';
                    legend.style.height = '31vh';
                    legend.style.minHeight = '13.5rem';
                    legend.style.maxHeight = '20rem';
                    const hasSwap = swapBtn && swapBtn.style.display !== 'none';
                    legend.style.padding = hasSwap ? '0.85rem 0.65rem 2.6rem 0.65rem' : '0.85rem 0.65rem 0.85rem 0.65rem';
                }
                if (scaleWrapper) scaleWrapper.style.display = 'none';
                if (invertGroup) invertGroup.style.display = 'none';
                const bodyWrapper = document.getElementById('legend-body-wrapper');
                if (bodyWrapper) bodyWrapper.style.display = 'none';
                
                const savedScrollTop = clusterList.scrollTop || 0;
                window._lastPresentLabels = presentLabels;
                
                if (!window._currentLegendMode || window._currentLegendMode === 'clusters' || window._currentLegendMode === 'earthquakes') {
                    window._currentLegendMode = 'clusters';
                    clusterList.style.display = 'flex';
                    const container = document.getElementById('legend-container');
                    if (container) container.style.display = 'none';
                    document.getElementById('legend-title').textContent = 'Clusters';
                }
                
                if (window.SeismicUI && typeof window.SeismicUI.updateSwapLegendVisibility === 'function') {
                    window.SeismicUI.updateSwapLegendVisibility();
                }

                if (!presentLabels || presentLabels.length === 0) {
                    clusterList.innerHTML = '';
                    return;
                }

                const uniqueLabels = [...new Set(presentLabels)]
                    .filter(l => l !== -1 && l !== undefined && l !== null)
                    .sort((a, b) => a - b);
                
                let html = '';
                if (uniqueLabels.length > 0) {
                    html += `
                        <div style="display:flex; gap:0.35rem; width:100%; margin-bottom:0.35rem; flex-shrink:0;">
                            <button class="btn-cluster-action btn-cluster-lock" onclick="lockAllClustersAnim()" title="Blocca tutti i cluster">Lock All</button>
                            <button class="btn-cluster-action btn-cluster-unlock" onclick="unlockAllClustersAnim()" title="Sblocca tutti i cluster">Unlock All</button>
                        </div>
                        <div style="margin-bottom:0.45rem; width:100%; flex-shrink:0;">
                            <button class="btn-cluster-subcluster" onclick="subclusterUnlockedAnim()" title="Perform subclustering on unlocked clusters">Subclustering</button>
                        </div>
                    `;
                }

                uniqueLabels.forEach((lbl, index) => {
                    const color = getClusterColor(lbl);
                    let labelText = `Cluster ${index + 1}`;
                    const isLocked = window.lockedClustersAnim.has(lbl);
                    const lockBtnStyle = isLocked
                        ? "background:rgba(245,158,11,0.25); border:1px solid rgba(245,158,11,0.6); color:#fcd34d;"
                        : "background:rgba(255,255,255,0.1); border:1px solid rgba(255,255,255,0.2); color:#fff;";
                    const lockText = isLocked ? "Locked" : "Unlocked";
                    
                    html += `
                        <div class="legend-item-cluster" style="display:flex; align-items:center; justify-content:space-between; gap:0.5rem; flex-shrink:0; width:100%; margin-bottom: 0.35rem;">
                            <span style="font-family:inherit;font-size:0.75rem;font-weight:600;color:#fff;opacity:0.9;">${labelText}</span>
                            <div style="display:flex; align-items:center; gap:0.35rem;">
                                <button class="btn-cluster-item-lock" onclick="toggleClusterLockAnim(${lbl})" style="${lockBtnStyle}" title="Toggle lock state">${lockText}</button>
                                <div style="width:0.875rem;height:0.875rem;border-radius:50%;background-color:${color};border:1px solid rgba(255,255,255,0.4);box-shadow:0 0 0.375rem ${color}80;"></div>
                            </div>
                        </div>
                    `;
                });
                clusterList.innerHTML = html;
                if (savedScrollTop > 0) {
                    clusterList.scrollTop = savedScrollTop;
                }
            }

            window.analyzeCluster = async function(lbl) {
                const overlay = document.getElementById('filter-loader');
                overlay.classList.add('show');

                let targetIndices = [];
                let contextIndices = [];
                if (animClustersMap && typeof currentStepIdx !== 'undefined') {
                    const dateStr = dates[currentStepIdx];
                    const frameData = animClustersMap[dateStr];
                    if (frameData && frameData.labels && frameData.indices) {
                        contextIndices = frameData.indices;
                        for (let i = 0; i < frameData.labels.length; i++) {
                            if (frameData.labels[i] === lbl) {
                                targetIndices.push(frameData.indices[i]);
                            }
                        }
                    }
                }

                if (targetIndices.length === 0) {
                    console.error("No points found for cluster " + lbl + " in current frame.");
                    overlay.classList.remove('show');
                    return;
                }

                try {
                    const params = {
                        kmeans_clusters: pClustersAnim.value,
                        kmeans_max_dist: pDistAnim.value,
                        dbscan_eps: pEpsAnim.value,
                        dbscan_min_samples: pMinAnim.value
                    };
                    await pywebview.api.load_subcluster_view(targetIndices, contextIndices, currentAnimClustMethod, params);
                } catch(e) {
                    console.error("Failed to load subcluster view:", e);
                    if (typeof showStatusToast === 'function') showStatusToast('Engine failure: ' + e);
                }
                setTimeout(() => overlay.classList.remove('show'), 2000);
            };

                       function generatePlaneTraces(planes, activeLabels = []) {
                if (!planes || planes.length === 0) return [];

                const uniqueLabels = [...new Set(activeLabels)]
                    .filter(l => l !== -1 && l !== undefined && l !== null)
                    .sort((a, b) => a - b);
                    
                const traces = [];

                planes.forEach(p => {
                    let hex, color;
                    if (p.grid_id.startsWith('cluster_')) {
                        const parts = p.grid_id.split('_');
                        const clusterIdx = parseInt(parts[1]);
                        hex = getClusterColor(clusterIdx);
                        const r = parseInt(hex.slice(1, 3), 16);
                        const g = parseInt(hex.slice(3, 5), 16);
                        const b = parseInt(hex.slice(5, 7), 16);
                        color = `rgba(${r}, ${g}, ${b}, 0.6)`;
                    } else {
                        const dateStr = p.grid_id.split('_').pop();
                        const dIdx = Math.max(0, dates.indexOf(dateStr));
                        const val01 = dates.length > 1 ? dIdx / (dates.length - 1) : 0.5;
                        hex = getHexFromScale(currentColorScale, val01);
                        const r = parseInt(hex.slice(1, 3), 16);
                        const g = parseInt(hex.slice(3, 5), 16);
                        const b = parseInt(hex.slice(5, 7), 16);
                        color = `rgba(${r}, ${g}, ${b}, 0.6)`;
                    }
                    
                    const dateParts = p.grid_id.split('_').pop().split('-');
                    const dateFmt = dateParts.length === 3 ? `${dateParts[2]}-${dateParts[1]}-${dateParts[0]}` : p.grid_id.split('_').pop();
                    
                    let title;
                    if (p.grid_id.startsWith('cluster_')) {
                        const rawId = parseInt(p.grid_id.split('_')[1]);
                        title = `${formatClusterDisplayLabel(rawId, uniqueLabels)} Plane`;
                    } else {
                        title = `Structural Plane (${dateFmt})`;
                    }
                    const strikeStr = p.strike !== undefined ? `Strike: ${p.strike.toFixed(1)}\u00b0<br>` : '';
                    const dipStr = p.dip !== undefined ? `Dip: ${p.dip.toFixed(1)}\u00b0<br>` : '';
                    const ddStr = p.dip_dir !== undefined ? `Dip Dir: ${p.dip_dir.toFixed(1)}\u00b0<br>` : '';
                    
                    let innerText = '';
                    if (p.equation) {
                        const eq = p.equation;
                        const fmt = (val) => (val >= 0 ? '+' : '') + val.toFixed(2);
                        const eqStr = `${fmt(eq.a)}x ${fmt(eq.b)}y ${fmt(eq.c)}z ${fmt(eq.d)} = 0`;
                        innerText = `<b>${title}</b><br>${strikeStr}${dipStr}${ddStr}Plane Equation:<br>${eqStr}<br>(x:Lon, y:Lat, z:Depth)`;
                    } else {
                        innerText = `<b>${title}</b><br>${strikeStr}${dipStr}${ddStr}`;
                    }

                    const gridSizeU = 20;
                    const gridSizeV = 15;
                    const vx = [], vy = [], vz = [], vText = [];
                    const fi = [], fj = [], fk = [], fColors = [];
                    const v0 = {x: p.x[0], y: p.y[0], z: p.z[0]};
                    const v1 = {x: p.x[1], y: p.y[1], z: p.z[1]};
                    const v2 = {x: p.x[2], y: p.y[2], z: p.z[2]};
                    const v3 = {x: p.x[3], y: p.y[3], z: p.z[3]};

                    for (let i = 0; i < gridSizeU; i++) {
                        for (let j = 0; j < gridSizeV; j++) {
                            const u = i / (gridSizeU - 1);
                            const v = j / (gridSizeV - 1);
                            vx.push((1-u)*(1-v)*v0.x + u*(1-v)*v1.x + u*v*v2.x + (1-u)*v*v3.x);
                            vy.push((1-u)*(1-v)*v0.y + u*(1-v)*v1.y + u*v*v2.y + (1-u)*v*v3.y);
                            vz.push((1-u)*(1-v)*v0.z + u*(1-v)*v1.z + u*v*v2.z + (1-u)*v*v3.z);
                            vText.push(innerText);
                        }
                    }

                    for (let i = 0; i < gridSizeU - 1; i++) {
                        for (let j = 0; j < gridSizeV - 1; j++) {
                            const p1 = i * gridSizeV + j;
                            const p2 = p1 + 1;
                            const p3 = p1 + gridSizeV;
                            const p4 = p3 + 1;
                            fi.push(p1, p2);
                            fj.push(p2, p4);
                            fk.push(p3, p3);
                            fColors.push(color, color);
                        }
                    }

                    traces.push({
                        type: 'mesh3d',
                        x: vx, y: vy, z: vz,
                        i: fi, j: fj, k: fk,
                        facecolor: fColors,
                        text: vText,
                        hoverinfo: 'text',
                        hoverlabel: { bgcolor: hex, font: { color: 'white', size: 12 } },
                        opacity: 0.8, visible: true, showlegend: false,
                        name: title,
                        lighting: { ambient: 0.9, diffuse: 0.5, specular: 0.1, roughness: 0.9, fresnel: 0.1 },
                        flatshading: true
                    });
                });

                return traces;
            };

            function generateHullTraces(planes, mode) {
                if (!planes || planes.length === 0) return [];
                
                const traces = [];
                const showWire = mode === 'wireframe' || mode === 'both';
                const showSolid = mode === 'solid' || mode === 'both';

                planes.forEach(p => {
                    if (!p.hull) return;
                    
                    let color = '#888888';
                    let clusterIdx = -1;
                    if (p.grid_id.startsWith('cluster_')) {
                        clusterIdx = parseInt(p.grid_id.split('_')[1]);
                        color = getClusterColor(clusterIdx);
                    }
                    const title = clusterIdx >= 0 ? `Cluster ${clusterIdx}` : 'Cluster ?';

                    if (showWire) {
                        const lx = [], ly = [], lz = [];
                        p.hull.simplices.forEach(s => {
                            for (const c of [[0,1], [1,2], [2,0]]) {
                                lx.push(p.hull.x[s[c[0]]], p.hull.x[s[c[1]]], null);
                                ly.push(p.hull.y[s[c[0]]], p.hull.y[s[c[1]]], null);
                                lz.push(p.hull.z[s[c[0]]], p.hull.z[s[c[1]]], null);
                            }
                        });
                        traces.push({
                            type: 'scatter3d',
                            x: lx, y: ly, z: lz,
                            mode: 'lines',
                            line: {color: color, width: 2},
                            opacity: 0.4,
                            name: title + ' Wire',
                            visible: true, showlegend: false, hoverinfo: 'skip'
                        });
                    }

                    if (showSolid) {
                        const fi = [], fj = [], fk = [];
                        p.hull.simplices.forEach(s => {
                            fi.push(s[0]); fj.push(s[1]); fk.push(s[2]);
                        });
                        traces.push({
                            type: 'mesh3d',
                            x: p.hull.x, y: p.hull.y, z: p.hull.z,
                            i: fi, j: fj, k: fk,
                            color: color,
                            opacity: 0.15,
                            name: title + ' Solid',
                            visible: true, showlegend: false, hoverinfo: 'skip'
                        });
                    }
                });

                return traces;
            }

            async function syncPlanes() {
                if (!planesEnabled) return;
                
                try {
                    const reqData = {
                        radius_km: parseFloat(planeRadius.value),
                        min_pts: parseInt(planeMinPts.value),
                        window_days: quakeData.window_days,
                        step_days: quakeData.step_days,
                        anim_mode: quakeData.anim_mode
                    };
                    let result = null;
                    if (window.seismicSocket) {
                        try {
                            result = await window.seismicSocket.sendRequest('get_structural_planes', reqData);
                        } catch (sErr) {
                            console.warn("Socket structural planes failed, checking desktop API:", sErr);
                        }
                    }

                    if (!result) {
                        const api = (window.pywebview && window.pywebview.api) || 
                                    (window.parent && window.parent.pywebview && window.parent.pywebview.api);
                        if (api && typeof api.get_structural_planes === 'function') {
                            try {
                                result = await api.get_structural_planes(reqData.radius_km, reqData.min_pts, reqData.window_days, reqData.anim_mode, reqData.step_days);
                            } catch (aErr) {
                                console.error("Desktop API get_structural_planes failed:", aErr);
                            }
                        }
                    }
                    
                    if (result && !result.error) {
                        structuralPlanes = result;
                        persistentPlanesMap.clear();
                        lastAccumIdx = -1;
                        await updateView(currentStepIdx);
                    } else {
                        console.error("Plane Calculation Error:", result?.error);
                    }
                } catch (e) {
                    console.error("Bridge Error:", e);
                } finally {
                    // No loader here, managed by caller
                }
            }


            let lastFrameTime = 0;
            async function animationLoop(timestamp) {
                if (!isPlaying) return;
                
                // If still rendering previous frame, skip this one to keep UI responsive
                if (isRendering) {
                    animId = requestAnimationFrame(animationLoop);
                    return;
                }

                const now = performance.now();
                if (!lastFrameTime) {
                    lastFrameTime = now;
                }

                const mult = (typeof speedMult === 'number' && speedMult > 0) ? speedMult : 1;
                let durationMs = 1000;
                let step = 1;

                if (quakeData.anim_mode === 'block') {
                    const secPerFrameInput = document.getElementById('sec-per-frame');
                    const baseSec = (secPerFrameInput && parseFloat(secPerFrameInput.value)) ? parseFloat(secPerFrameInput.value) : 1.0;
                    durationMs = Math.max(40, Math.round((baseSec * 1000) / mult));
                    step = 1;
                } else {
                    const targetMs = 1000 / mult;
                    if (targetMs >= 40) {
                        durationMs = Math.round(targetMs);
                        step = 1;
                    } else {
                        durationMs = 40;
                        step = Math.max(1, Math.round(40 / targetMs));
                    }
                }

                const totalFrames = dates.length;
                if (now - lastFrameTime >= durationMs) {
                    if (now - lastFrameTime > durationMs * 2) {
                        lastFrameTime = now;
                    } else {
                        lastFrameTime += durationMs;
                    }

                    let targetIdx = currentStepIdx + step;
                    
                    if (targetIdx < totalFrames) {
                        try {
                            await updateView(targetIdx);
                        } catch (e) {
                            console.error("Animation loop error:", e);
                        }
                        slider.value = currentStepIdx;
                    } else {
                        if (currentStepIdx !== totalFrames - 1) {
                            try {
                                await updateView(totalFrames - 1);
                            } catch (e) {
                                console.error("Animation loop error:", e);
                            }
                            slider.value = currentStepIdx;
                        }
                        pause();
                        return;
                    }
                }
                animId = requestAnimationFrame(animationLoop);
            }

            function setAnimationControlsLock(locked) {
                const elementsToLock = [
                    'settings-bar', 'apply-all-btn',
                    'jump-bar', 'filter-bar', 'jump-date', 'jump-btn',
                    'camera-controls',
                    'glass-legend', 'legend-container', 'cluster-list', 'btn-swap-legend',
                    'back-btn', 'info-btn', 'overlay-btn', 'screenshot-btn',
                    'btn-export-clusters'
                ];
                elementsToLock.forEach(id => {
                    const el = document.getElementById(id);
                    if (el) {
                        if (locked) el.classList.add('anim-locked');
                        else el.classList.remove('anim-locked');
                    }
                });
                document.querySelectorAll('#camera-controls button, #camera-controls .btn-cam, .layer-btn, .layer-toggle-btn, .layer-apply-btn, .settings-btn').forEach(el => {
                    if (el.id !== 'play-btn' && el.id !== 'pause-btn') {
                        if (locked) el.classList.add('anim-locked');
                        else el.classList.remove('anim-locked');
                    }
                });
            }

            async function play() {
                if (isPlaying) return;
                playBtn.classList.add('active');
                pauseBtn.classList.remove('active');
                
                const totalFrames = dates.length;
                if (currentStepIdx >= totalFrames - 1) {
                    currentStepIdx = 0;
                    try {
                        await updateView(0);
                    } catch (e) {
                        console.error("Play loop error:", e);
                    }
                }
                isPlaying = true;
                setAnimationControlsLock(true);
                lastFrameTime = performance.now(); 
                animId = requestAnimationFrame(animationLoop);
            }

            function pause() {
                isPlaying = false;
                playBtn.classList.remove('active');
                pauseBtn.classList.add('active');
                setAnimationControlsLock(false);
                
                if (animId) {
                    cancelAnimationFrame(animId);
                    animId = null;
                }
                lastFrameTime = 0; 
                
                // Explicitly stop cinema mode (auto-rotation) when pausing
                if (typeof cinemaModeActive !== 'undefined' && cinemaModeActive) {
                    toggleCinemaMode();
                }
            }



            playBtn.onclick = play;
            pauseBtn.onclick = pause;
            window.togglePlayAnimation = () => {
                if (isPlaying) {
                    pause();
                } else {
                    play();
                }
            };
            window.isAnimationPlaying = () => isPlaying;
            window.pauseAnimation = pause;
            window.getCurrentFrameClusterExportData = function() {
                if (!animClusteringEnabled || !animClustersMap) return null;
                return window._currentFrameClusterExportData || null;
            };

            let sliderRafId = null;
            slider.oninput = () => {
                pause();
                const targetIdx = parseInt(slider.value, 10);
                updateCurrentDateDisplay(targetIdx);
                if (jumpDate && dates && dates[targetIdx] && document.activeElement !== jumpDate) {
                    jumpDate.value = dates[targetIdx];
                }
                if (sliderRafId) cancelAnimationFrame(sliderRafId);
                sliderRafId = requestAnimationFrame(() => {
                    sliderRafId = null;
                    updateView(targetIdx);
                });
            };

            // Menus

            SeismicUI.initMenu(speedToggle, speedMenu);
            SeismicUI.initMenu(colorToggle, colorMenu);
            SeismicUI.initMenu(sizeToggle, sizeMenu);

            const animDisplayToggle = document.getElementById('anim-display-toggle');
            const animDisplayMenu = document.getElementById('anim-display-menu');
            let currentAnimDisplayMode = 'wireframe';
            
            if (animDisplayToggle && animDisplayMenu) {
                SeismicUI.initMenu(animDisplayToggle, animDisplayMenu);
                SeismicUI.bindMenu(animDisplayMenu, (item) => {
                    currentAnimDisplayMode = item.dataset.mode;
                    animDisplayToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
                });
            }

            SeismicUI.bindMenu(sizeMenu, (item) => {
                currentSizeMode = item.dataset.mode;
                sizeToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
            });

            SeismicUI.bindMenu(speedMenu, (item) => {
                speedMult = parseFloat(item.dataset.val);
                speedToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
            });

            SeismicUI.bindMenu(colorMenu, (item) => {
                currentMode = item.dataset.mode;
                colorToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
                if (typeof updateView === 'function') {
                    updateView(currentStepIdx);
                }
            });

            window.setEarthquakeScale = function(scale) {
                currentColorScale = scale;
                if (window.SeismicUI && window.SeismicUI._layerScales) {
                    window.SeismicUI._layerScales.earthquakes = scale;
                }
                const gd = document.getElementById('plot') || document.querySelector('.plotly-graph-div');
                const pScale = (typeof window.getPlotlyScale === 'function' ? window.getPlotlyScale(currentColorScale) : (typeof getPlotlyScale === 'function' ? getPlotlyScale(currentColorScale) : 'Viridis'));
                if (gd && gd.data) {
                    for (let i = 1; i <= 3; i++) {
                        if (gd.data[i] && gd.data[i].marker) {
                            gd.data[i].marker.colorscale = pScale;
                            gd.data[i].marker.reversescale = invertScale;
                        }
                    }
                    try { Plotly.redraw(gd); } catch (e) {}
                }
                if (typeof updateView === 'function') {
                    updateView(currentStepIdx);
                }
            };

            window.setEarthquakeInvert = function(inv) {
                invertScale = inv;
                if (window.SeismicUI && window.SeismicUI._layerInverts) {
                    window.SeismicUI._layerInverts.earthquakes = invertScale;
                }
                const gd = document.getElementById('plot') || document.querySelector('.plotly-graph-div');
                if (gd && gd.data) {
                    for (let i = 1; i <= 3; i++) {
                        if (gd.data[i] && gd.data[i].marker) {
                            gd.data[i].marker.reversescale = invertScale;
                        }
                    }
                    try { Plotly.redraw(gd); } catch (e) {}
                }
                if (typeof updateView === 'function') updateView(currentStepIdx);
            };
            window.updateView = (idx) => updateView(typeof idx !== 'undefined' ? idx : currentStepIdx);

            if (jumpBtn) {
                jumpBtn.onclick = () => {
                    const target = jumpDate.value ? jumpDate.value.trim() : '';
                    if (!target) return;
                    
                    const idx = dates.findIndex(d => d >= target);
                    if (idx !== -1) {
                        pause();
                        updateView(idx);
                    } else {
                        pause();
                        updateView(dates.length - 1);
                    }
                };
            }

            // Plane Controls
            let lastCheckedAnalysis = null;
            function syncAnalysisModes() {
                planeControls.style.display = showPlanesCheck.checked ? 'block' : 'none';
                animClustControls.style.display = showAnimClustCheck.checked ? 'block' : 'none';
            }
            function handleAnalysisRadioClick(e) {
                if (lastCheckedAnalysis === this) {
                    this.checked = false;
                    lastCheckedAnalysis = null;
                } else {
                    lastCheckedAnalysis = this;
                }
                syncAnalysisModes();
            }

            showPlanesCheck.onclick = handleAnalysisRadioClick;

            accumulatePlanesCheck.onchange = () => {
                accumulatePlanes = accumulatePlanesCheck.checked;
            };

            // Plane Radius/MinPts updates (using inputs now)
            planeRadius.onchange = () => {
                if (planeRadius.value < 0.1) planeRadius.value = 0.1;
            };
            planeMinPts.onchange = () => {
                if (planeMinPts.value < 3) planeMinPts.value = 3;
            };

            // Animated Clustering Controls
            const showAnimClustCheck = document.getElementById('anim-show-clustering');
            const animClustControls = document.getElementById('anim-clustering-controls');
            const animMethodToggle = document.getElementById('anim-method-toggle');
            const animMethodMenu = document.getElementById('anim-method-menu');
            const pClustersAnim = document.getElementById('anim-param-clusters');
            const pDistAnim = document.getElementById('anim-param-dist');
            const pEpsAnim = document.getElementById('anim-param-eps');
            const pMinAnim = document.getElementById('anim-param-min-samples');
            const showAnimPlanesCheck = document.getElementById('anim-show-cluster-planes');
            const calcFramesAnim = document.getElementById('anim-calc-frames');
            const animKmeansParams = document.getElementById('anim-kmeans-params');
            const animDbscanParams = document.getElementById('anim-dbscan-params');
            const useCylindersCheck = document.getElementById('anim-use-cylinders');
            const cylinderOptions = document.getElementById('anim-cylinder-options');
            const pCylinderRadius = document.getElementById('anim-cylinder-radius');

            useCylindersCheck.onchange = () => {
                cylinderOptions.style.display = useCylindersCheck.checked ? 'block' : 'none';
            };

            showAnimClustCheck.onclick = handleAnalysisRadioClick;

            const animCalcFramesContainer = document.getElementById('anim-calc-frames-container');
            const animAccumulatePlanesContainer = document.getElementById('anim-accumulate-planes-container');
            const animAccumulatePlanesCheck = document.getElementById('anim-accumulate-planes');
            
            animAccumulatePlanesCheck.onchange = () => {
                accumulatePlanes = animAccumulatePlanesCheck.checked;
                accumulatePlanesCheck.checked = accumulatePlanes; // sync with structural one
            };
            
            accumulatePlanesCheck.onchange = () => {
                accumulatePlanes = accumulatePlanesCheck.checked;
                if (animAccumulatePlanesCheck) animAccumulatePlanesCheck.checked = accumulatePlanes; // sync back
            };

            showAnimPlanesCheck.onchange = () => {
                showAnimClusterPlanes = showAnimPlanesCheck.checked;
                const isVisible = showAnimPlanesCheck.checked ? 'block' : 'none';
                animCalcFramesContainer.style.display = isVisible;
                animAccumulatePlanesContainer.style.display = isVisible;
            };
            showAnimPlanesCheck.onchange();

            SeismicUI.initMenu(animMethodToggle, animMethodMenu);
            SeismicUI.bindMenu(animMethodMenu, (item) => {
                currentAnimClustMethod = item.dataset.val;
                animMethodToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
                animKmeansParams.style.display = currentAnimClustMethod === 'kmeans' ? 'block' : 'none';
                animDbscanParams.style.display = currentAnimClustMethod === 'dbscan' ? 'block' : 'none';
                
            });

            async function syncAnimatedClustering() {
                try {
                    const magMinVal = document.getElementById('anim-mag-min') ? document.getElementById('anim-mag-min').value : '-10';
                    const magMaxVal = document.getElementById('anim-mag-max') ? document.getElementById('anim-mag-max').value : '10';
                    const depMinVal = document.getElementById('anim-dep-min') ? document.getElementById('anim-dep-min').value : '-100';
                    const depMaxVal = document.getElementById('anim-dep-max') ? document.getElementById('anim-dep-max').value : '1000';
                    const cylDepthVal = document.getElementById('anim-cylinder-depth') ? document.getElementById('anim-cylinder-depth').value : '0';

                    const params = {
                        anim_mode: quakeData.anim_mode || 'accumulation',
                        window_days: quakeData.window_days || 30,
                        step_days: quakeData.step_days || 7,
                        kmeans_clusters: pClustersAnim ? pClustersAnim.value : 3,
                        kmeans_max_dist: pDistAnim ? pDistAnim.value : 0,
                        dbscan_eps: pEpsAnim ? pEpsAnim.value : 500,
                        dbscan_min_samples: pMinAnim ? pMinAnim.value : 5,
                        show_cluster_planes: showAnimPlanesCheck.checked || (typeof currentAnimDisplayMode !== 'undefined' && currentAnimDisplayMode !== 'points'),
                        mag_min: magMinVal,
                        mag_max: magMaxVal,
                        dep_min: depMinVal,
                        dep_max: depMaxVal,
                        use_cylinders: useCylindersCheck ? useCylindersCheck.checked : false,
                        cylinder_radius: pCylinderRadius ? pCylinderRadius.value : 0.5,
                        cylinder_depth_step: cylDepthVal
                    };
                    const planeStep = parseInt(calcFramesAnim ? calcFramesAnim.value : 5) || 5;

                    let res = null;
                    if (window.seismicSocket) {
                        try {
                            res = await window.seismicSocket.sendRequest('get_animated_clustering', {
                                method: currentAnimClustMethod,
                                params: params,
                                plane_step: planeStep
                            });
                        } catch (sErr) {
                            console.warn("Socket animated clustering failed, checking desktop API fallback:", sErr);
                        }
                    }

                    if (!res) {
                        const api = (window.pywebview && window.pywebview.api) || 
                                    (window.parent && window.parent.pywebview && window.parent.pywebview.api);
                        if (api && typeof api.get_animated_clustering === 'function') {
                            try {
                                res = await api.get_animated_clustering(currentAnimClustMethod, params, planeStep);
                            } catch (aErr) {
                                console.error("Desktop API animated clustering failed:", aErr);
                            }
                        }
                    }

                    if (res && !res.error) {
                        animClustersMap = res;
                        window.animClustersMap = res;
                    } else if (res && res.error) {
                        console.error("Clustering Error:", res.error);
                        if (typeof showStatusToast === 'function') showStatusToast(res.error, false);
                    } else {
                        console.error("Clustering failed: no response received.");
                        if (typeof showStatusToast === 'function') showStatusToast("Failed to calculate clustering.", false);
                    }
                } catch (e) {
                    console.error("Bridge Error:", e);
                }
            }

            const filterLoader = document.getElementById('filter-loader');

            async function applyAllChanges() {
                const magMinVal = parseFloat(document.getElementById('anim-mag-min').value);
                const magMaxVal = parseFloat(document.getElementById('anim-mag-max').value);
                const depMinVal = parseFloat(document.getElementById('anim-dep-min').value);
                const depMaxVal = parseFloat(document.getElementById('anim-dep-max').value);

                appliedMagMin = isNaN(magMinVal) ? -10 : magMinVal;
                appliedMagMax = isNaN(magMaxVal) ? 10 : magMaxVal;
                appliedDepMin = isNaN(depMinVal) ? -100 : depMinVal;
                appliedDepMax = isNaN(depMaxVal) ? 1000 : depMaxVal;

                filterLoader.classList.add('show');
                
                // Minimal delay to ensure the loader is painted before blocking the thread
                setTimeout(async () => {
                    try {
                        if (!gd) {
                            filterLoader.classList.remove('show');
                            return;
                        }
                        
                        // 1. Update Colors (Visibility)
                        const traceIdx = (currentMode === 'mag') ? 1 : (currentMode === 'date' ? 2 : 3);
                        Plotly.restyle(gd, { visible: [false, false, false] }, [1, 2, 3]);
                        Plotly.restyle(gd, { visible: [true] }, [traceIdx]);
                        
                        // 2. Update Histogram
                        renderHistogram();
                        
                        // 3. Update applied analysis states on Apply Changes
                        animClusteringEnabled = showAnimClustCheck.checked;
                        window.animClusteringEnabled = animClusteringEnabled;
                        planesEnabled = showPlanesCheck.checked;

                        
                        

                        if (animClusteringEnabled) {
                            window._currentLegendMode = 'clusters';
                            await syncAnimatedClustering();
                        } else if (planesEnabled) {
                            await syncPlanes();
                        } else {
                            // Delete all plane traces (4+)
                            const ids = [];
                            for (let t = gd.data.length - 1; t >= 4; t--) {
                                if (gd.data[t]) {
                                    ids.push(t);
                                }
                            }
                            if (ids.length > 0) {
                                Plotly.deleteTraces(gd, ids);
                            }
                            Plotly.addTraces(gd, {
                                type: 'mesh3d', x: [], y: [], z: [],
                                i: [], j: [], k: [],
                                visible: false, showlegend: false,
                                hoverinfo: 'text', name: 'Structural Planes'
                            });
                            persistentPlanesMap.clear();
                            lastAccumIdx = -1;
                            animClustersMap = null;
                            window.animClustersMap = null;
                            if (window._currentLegendMode === 'clusters') {
                                window._currentLegendMode = 'earthquakes';
                            }
                        }

                        // 4. Final render update
                        await updateView(currentStepIdx);
                        if (window.SeismicUI && typeof window.SeismicUI.updateSwapLegendVisibility === 'function') {
                            window.SeismicUI.updateSwapLegendVisibility();
                        }

                    } catch (err) {
                        console.error("Apply Changes Error:", err);
                        if (typeof showStatusToast === 'function') showStatusToast('Error applying changes.');
                    } finally {
                        filterLoader.classList.remove('show');
                    }
                }, 30);
            }

            document.getElementById('apply-all-btn').onclick = applyAllChanges;

            // Snapshot baseline defaults from when this animated visualization opened
            const initialAnimDefaults = {
                magMin: magMinInput ? magMinInput.value : '',
                magMax: magMaxInput ? magMaxInput.value : '',
                depMin: depMinInput ? depMinInput.value : '',
                depMax: depMaxInput ? depMaxInput.value : '',
                planeRadius: planeRadius ? planeRadius.value : '0.5',
                planeMinPts: planeMinPts ? planeMinPts.value : '4',
                accumulatePlanes: false,
                showPlanes: false,
                showClustering: false,
                clusterMethod: 'dbscan',
                dbscanEps: pEpsAnim ? pEpsAnim.value : '500',
                dbscanMinSamples: pMinAnim ? pMinAnim.value : '5',
                kmeansClusters: pClustersAnim ? pClustersAnim.value : '3',
                kmeansDist: pDistAnim ? pDistAnim.value : '0',
                displayMode: 'wireframe',
                showClusterPlanes: false,
                calcFrames: calcFramesAnim ? calcFramesAnim.value : '5',
                useCylinders: false,
                cylinderRadius: pCylinderRadius ? pCylinderRadius.value : '0.5',
                cylinderDepth: document.getElementById('anim-cylinder-depth') ? document.getElementById('anim-cylinder-depth').value : '0',
                };

            const resetAllBtn = document.getElementById('reset-all-btn');
            if (resetAllBtn) {
                resetAllBtn.onclick = async (e) => {
                    e.preventDefault();
                    if (magMinInput) magMinInput.value = initialAnimDefaults.magMin;
                    if (magMaxInput) magMaxInput.value = initialAnimDefaults.magMax;
                    if (depMinInput) depMinInput.value = initialAnimDefaults.depMin;
                    if (depMaxInput) depMaxInput.value = initialAnimDefaults.depMax;

                    if (planeRadius) planeRadius.value = initialAnimDefaults.planeRadius;
                    if (planeMinPts) planeMinPts.value = initialAnimDefaults.planeMinPts;
                    const pAcc = document.getElementById('accumulate-planes');
                    if (pAcc) pAcc.checked = initialAnimDefaults.accumulatePlanes;
                    if (animAccumulatePlanesCheck) animAccumulatePlanesCheck.checked = initialAnimDefaults.accumulatePlanes;
                    accumulatePlanes = initialAnimDefaults.accumulatePlanes;

                    // Clustering parameters
                    currentAnimClustMethod = initialAnimDefaults.clusterMethod;
                    if (animMethodToggle) animMethodToggle.textContent = 'DBSCAN ▾';
                    if (animMethodMenu) {
                        animMethodMenu.querySelectorAll('.menu-item').forEach(i => {
                            i.classList.toggle('active', i.dataset.val === 'dbscan');
                        });
                    }
                    if (animKmeansParams) animKmeansParams.style.display = 'none';
                    if (animDbscanParams) animDbscanParams.style.display = 'block';
                    

                    if (pEpsAnim) pEpsAnim.value = initialAnimDefaults.dbscanEps;
                    if (pMinAnim) pMinAnim.value = initialAnimDefaults.dbscanMinSamples;
                    
                    
                    
                    if (pClustersAnim) pClustersAnim.value = initialAnimDefaults.kmeansClusters;
                    if (pDistAnim) pDistAnim.value = initialAnimDefaults.kmeansDist;

                    if (showAnimPlanesCheck) {
                        showAnimPlanesCheck.checked = initialAnimDefaults.showClusterPlanes;
                        showAnimPlanesCheck.onchange();
                    }
                    if (calcFramesAnim) calcFramesAnim.value = initialAnimDefaults.calcFrames;

                    if (useCylindersCheck) {
                        useCylindersCheck.checked = initialAnimDefaults.useCylinders;
                        useCylindersCheck.onchange();
                    }
                    if (pCylinderRadius) pCylinderRadius.value = initialAnimDefaults.cylinderRadius;
                    const pCylDepth = document.getElementById('anim-cylinder-depth');
                    if (pCylDepth) pCylDepth.value = initialAnimDefaults.cylinderDepth;

                    if (showPlanesCheck) showPlanesCheck.checked = initialAnimDefaults.showPlanes;
                    if (showAnimClustCheck) showAnimClustCheck.checked = initialAnimDefaults.showClustering;

                    const planeCtrl = document.getElementById('plane-controls');
                    if (planeCtrl) planeCtrl.style.display = initialAnimDefaults.showPlanes ? 'block' : 'none';
                    const clustCtrl = document.getElementById('anim-clustering-controls');
                    if (clustCtrl) clustCtrl.style.display = initialAnimDefaults.showClustering ? 'block' : 'none';

                    if (typeof showStatusToast === 'function') {
                        showStatusToast("Parameters reset to default values", true);
                    }

                    await applyAllChanges();
                };
            }

            // Ensure Plane Trace (Trace 4) is present if not already added by Python
            if (gd.data.length < 5) {
                Plotly.addTraces(gd, {
                    type: 'mesh3d',
                    x: [], y: [], z: [],
                    i: [], j: [], k: [],
                    opacity: 0.8,
                    color: '#00f3ff',
                    name: 'Structural Planes',
                    text: [],
                    hoverinfo: 'text',
                    hoverlabel: { bgcolor: 'rgba(30,30,50,0.9)', font: { color: 'white', size: 12 } },
                    visible: false,
                    lighting: { ambient: 0.9, diffuse: 0.5, specular: 0.1, roughness: 0.9, fresnel: 0.1 },
                    flatshading: true
                });
            }

            renderHistogram();
            updateView(0);
            updateCurrentDateDisplay(0);

            // Explicit initial Glass Legend sync for animated view
            setTimeout(() => {
                const initialTitle = currentMode === 'dep' ? 'Depth (KM)' : (currentMode === 'mag' ? 'Magnitude' : 'Date');
                const initialLimits = currentMode === 'dep' ? (quakeData.dep_range || [0, 100]) : (currentMode === 'mag' ? (quakeData.mag_range || [0, 10]) : (quakeData.date_range || [0, 1]));
                updateGlassLegend(
                    true,
                    initialTitle,
                    currentColorScale,
                    invertScale,
                    initialLimits,
                    { startDate: quakeData.start_date }
                );
            }, 60);

            // Show both structural panel and clustering panel in all modes
            document.getElementById('structural-settings-group').style.display = 'block';
            document.getElementById('clustering-settings-group').style.display = 'block';

            const speedDropdown = document.getElementById('playback-speed-dropdown-container');
            const speedInput = document.getElementById('playback-speed-input-container');
            const speedLabel = document.getElementById('playback-speed-label');
            if (quakeData.anim_mode === 'block') {
                if (speedDropdown) speedDropdown.style.display = 'none';
                if (speedInput) speedInput.style.display = 'block';
                if (speedLabel) speedLabel.textContent = 'Seconds per frame';
            }



            // Sync UI state and finally hide loader
            hideInitLoader();
        }

        window.addEventListener('load', function() {
            initAnimation().catch(err => {
                console.error('Failed to load animation data:', err);
                if (typeof showStatusToast === 'function') showStatusToast('Failed to load data.');
                hideInitLoader();
            });
        });
