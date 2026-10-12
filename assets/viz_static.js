const DATA_URL = (window.SEISMIC_CONFIG && window.SEISMIC_CONFIG.dataUrl) || '__DATA_URL__';

        async function initVisualization() {
            const quakeData = await fetchAndUnpackSeismicData(DATA_URL);
            window.quakeData = quakeData;

            const gd = document.querySelector('.plotly-graph-div');
            if (window.setupPassThroughTerrainHover) window.setupPassThroughTerrainHover(gd);
            const startInput = document.getElementById('filter-start');
            const endInput = document.getElementById('filter-end');
            const magMin = document.getElementById('mag-min');
            const magMax = document.getElementById('mag-max');
            const depMin = document.getElementById('dep-min');
            const depMax = document.getElementById('dep-max');
            const invertCheck = document.getElementById('invert-scale');
            
            const colorToggle = document.getElementById('color-toggle');
            const colorMenu = document.getElementById('color-menu');
            const viewModeToggle = document.getElementById('view-mode-toggle');
            const viewModeMenu = document.getElementById('view-mode-menu');
            const viewModeGroup = document.getElementById('view-mode-group');
            const applyBtn = document.getElementById('apply-filters-btn');


            const totalCount = quakeData.magnitude ? quakeData.magnitude.length : 0;
            const dates = (quakeData.times && Array.isArray(quakeData.times))
                ? quakeData.times.map(t => (t ? t.slice(0, 10) : ''))
                : new Array(totalCount).fill('');
            const uniqueDates = (quakeData.unique_dates && quakeData.unique_dates.length > 0)
                ? quakeData.unique_dates
                : Array.from(new Set(dates.filter(Boolean))).sort();

            if (!quakeData.hover || quakeData.hover.length !== totalCount) {
                const qLon = quakeData.longitude;
                const qLat = quakeData.latitude;
                const qMag = quakeData.magnitude;
                const qDep = quakeData.depth;
                const qTimes = quakeData.times;
                const N = totalCount;
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

            if (gd && gd.data && quakeData.hover) {
                const eqIndices = [];
                for (let i = 0; i < gd.data.length; i++) {
                    const tr = gd.data[i];
                    if (!tr) continue;
                    const name = tr.name || '';
                    if (name.includes('Earthquakes') ||
                        (tr.type === 'scatter3d' && tr.type !== 'surface' && tr.type !== 'mesh3d' &&
                         !name.includes('Stations') && !name.includes('Uplift') &&
                         !name.includes('Tomography') && !name.includes('Tomografia') && !name.includes('Surface'))) {
                        eqIndices.push(i);
                    }
                }
                if (eqIndices.length > 0) {
                    Plotly.restyle(gd, {
                        hovertext: [quakeData.hover],
                        text: [quakeData.hover],
                        hovertemplate: '%{hovertext}<extra></extra>'
                    }, eqIndices);
                }
            }

            if (uniqueDates.length > 0) {
                if (startInput) {
                    startInput.min = uniqueDates[0];
                    startInput.max = uniqueDates[uniqueDates.length - 1];
                    startInput.value = uniqueDates[0];
                }
                if (endInput) {
                    endInput.min = uniqueDates[0];
                    endInput.max = uniqueDates[uniqueDates.length - 1];
                    endInput.value = uniqueDates[uniqueDates.length - 1];
                }
            }

            if (quakeData.mag_range && quakeData.mag_range.length >= 2) {
                magMin.value = quakeData.mag_range[0].toFixed(1);
                magMax.value = quakeData.mag_range[1].toFixed(1);
            } else {
                let minM = Infinity, maxM = -Infinity;
                for (let i = 0; i < quakeData.magnitude.length; i++) {
                    const v = quakeData.magnitude[i];
                    if (v < minM) minM = v;
                    if (v > maxM) maxM = v;
                }
                magMin.value = (minM !== Infinity ? minM : 0).toFixed(1);
                magMax.value = (maxM !== -Infinity ? maxM : 10).toFixed(1);
            }

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

            let currentColorMode = 'dep';
            let currentColorScale = 'Viridis';
            let currentViewMode = 'points';

            let invertScale = false;

            // Snapshot baseline defaults from when this specific visualization opened
            const initialStaticDefaults = {
                startDate: startInput ? startInput.value : '',
                endDate: endInput ? endInput.value : '',
                magMin: magMin ? magMin.value : '',
                magMax: magMax ? magMax.value : '',
                depMin: depMin ? depMin.value : '',
                depMax: depMax ? depMax.value : ''
            };

            const is3D = (gd.layout.scene !== undefined);
            if (!is3D && gd.data.length > 1) viewModeGroup.style.display = 'block';

            if (!is3D) {
                // Store initial view after a small delay to ensure Plotly has initialized map / mapbox
                setTimeout(() => {
                    const mapLayout = gd.layout.mapbox || gd.layout.map;
                    if (mapLayout) {
                        window._initial2DMapboxView = {
                            center: { ...mapLayout.center },
                            zoom: mapLayout.zoom,
                            pitch: mapLayout.pitch || 0,
                            bearing: mapLayout.bearing || 0
                        };
                    }
                }, 500);
            }


            // Menus
            SeismicUI.initMenu(colorToggle, colorMenu);
            if (viewModeToggle) SeismicUI.initMenu(viewModeToggle, viewModeMenu);

            SeismicUI.bindMenu(colorMenu, (item) => {
                currentColorMode = item.dataset.mode;
                colorToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
                window._userExplicitColorSelection = true;
                applyFilterWithLoader();
            });

            let currentBarTitle = 'Depth (KM)';
            let currentLimits = quakeData.dep_limit || quakeData.dep_range || [0, 10];

            function applyColorRestyleOnly() {
                const gd = document.getElementById('plot') || document.querySelector('.plotly-graph-div');
                if (!gd || !gd.data) return;
                const pScale = (typeof window.getPlotlyScale === 'function') ? window.getPlotlyScale(currentColorScale) : getPlotlyScale(currentColorScale);
                
                let curTitle = 'Depth (KM)';
                let curLimits = quakeData.dep_limit || quakeData.dep_range || [0, 10];
                if (currentColorMode === 'mag') {
                    curTitle = 'Magnitude';
                    curLimits = quakeData.mag_limit || quakeData.mag_range || [0, 10];
                } else if (currentColorMode === 'date') {
                    curTitle = 'Date';
                    curLimits = quakeData.date_limit || quakeData.date_range || [0, 1];
                }

                if (is3D) {
                    for (let i = 0; i < gd.data.length; i++) {
                        const tr = gd.data[i];
                        if (!tr) continue;
                        const name = tr.name || '';
                        if (tr.type === 'scatter3d' && (
                            name.includes('Earthquakes') || name === 'Depth' || name === 'Date' || name === 'Magnitude' ||
                            (!name.includes('Stations') && !name.includes('Uplift') && !name.includes('Tomography') && !name.includes('Tomografia') && !name.includes('Vectors') && !name.includes('Arrow') && !name.includes('Terrain') && !name.includes('Mesh'))
                        )) {
                            if (!tr.marker) tr.marker = {};
                            tr.marker.colorscale = pScale;
                            tr.marker.reversescale = invertScale;
                            try {
                                Plotly.restyle(gd, {
                                    'marker.colorscale': [pScale],
                                    'marker.reversescale': [invertScale]
                                }, [i]);
                            } catch (e) {}
                        }
                    }
                    try { Plotly.redraw(gd); } catch (e) { try { Plotly.react(gd, gd.data, gd.layout); } catch (e2) {} }
                } else {
                    const isHeatmap = (currentViewMode === 'heatmap');
                    for (let i = 0; i < gd.data.length; i++) {
                        const tr = gd.data[i];
                        if (!tr) continue;
                        const name = tr.name || '';
                        const isDensity = (tr.type === 'densitymapbox' || tr.type === 'densitymap');
                        if (isHeatmap && (name.includes('Heatmap') || isDensity)) {
                            tr.colorscale = pScale;
                            tr.reversescale = invertScale;
                            try {
                                Plotly.restyle(gd, {
                                    'colorscale': [pScale],
                                    'reversescale': [invertScale]
                                }, [i]);
                            } catch (e) {}
                        } else if (!isHeatmap && (name.includes('Earthquakes') || ((tr.type === 'scattermapbox' || tr.type === 'scattermap') && !name.includes('Stations') && !name.includes('Uplift') && !name.includes('Tomography') && !name.includes('Tomografia')))) {
                            if (!tr.marker) tr.marker = {};
                            tr.marker.colorscale = pScale;
                            tr.marker.reversescale = invertScale;
                            try {
                                Plotly.restyle(gd, {
                                    'marker.colorscale': [pScale],
                                    'marker.reversescale': [invertScale]
                                }, [i]);
                            } catch (e) {}
                        }
                    }
                    try { Plotly.redraw(gd); } catch (e) { try { Plotly.react(gd, gd.data, gd.layout); } catch (e2) {} }
                }
                updateGlassLegend(
                    currentViewMode !== 'heatmap',
                    curTitle,
                    currentColorScale,
                    invertScale,
                    curLimits,
                    { startDate: quakeData.start_date }
                );
            }

            window.setEarthquakeScale = function(scale) {
                currentColorScale = scale;
                if (window.SeismicUI && window.SeismicUI._layerScales) {
                    window.SeismicUI._layerScales.earthquakes = scale;
                }
                applyColorRestyleOnly();
            };

            window.applyColorRestyleOnly = applyColorRestyleOnly;
            window.setEarthquakeInvert = function(inv) {
                invertScale = inv;
                if (window.SeismicUI && window.SeismicUI._layerInverts) {
                    window.SeismicUI._layerInverts.earthquakes = inv;
                }
                applyColorRestyleOnly();
            };

            if (viewModeMenu) {
                SeismicUI.bindMenu(viewModeMenu, (item) => {
                    currentViewMode = item.dataset.mode;
                    viewModeToggle.textContent = item.textContent.split(' ')[0] + ' ▾';
                    const isHeatmap = (currentViewMode === 'heatmap');
                    SeismicUI.setGroupDisabled(colorToggle.closest('.settings-group'), isHeatmap);
                    const invGroup = invertCheck ? (invertCheck.closest('.legend-invert-checkbox') || invertCheck.closest('.glass-checkbox')) : null;
                    if (invGroup) SeismicUI.setGroupDisabled(invGroup, isHeatmap);
                    const sizeGroup = document.getElementById('point-size-group');
                    if (sizeGroup) SeismicUI.setGroupDisabled(sizeGroup, isHeatmap);
                    applyFilter();
                });
            }


            const sizeToggle = document.getElementById('size-toggle');
            const sizeMenu = document.getElementById('size-menu');
            let currentSizeMode = is3D ? 'uniform' : 'magnitude';

            SeismicUI.initMenu(sizeToggle, sizeMenu);
            if (!is3D) {
                if (sizeToggle) sizeToggle.textContent = 'Magnitude ▾';
                if (sizeMenu) {
                    const items = sizeMenu.querySelectorAll('.menu-item');
                    items.forEach(i => {
                        if (i.dataset.mode === 'magnitude') i.classList.add('active');
                        else i.classList.remove('active');
                    });
                }
            }

            SeismicUI.bindMenu(sizeMenu, (item) => {
                currentSizeMode = item.dataset.mode;
                sizeToggle.textContent = item.textContent + ' ▾';
                applyFilterWithLoader();
            });

            const rangeApplyCallback = null;

            // Invert scale change is handled globally by SeismicUI.toggleInvertScale -> window.setEarthquakeInvert

            // Range input sanitization
            SeismicUI.setupBoundsValidation(magMin, magMin.value, rangeApplyCallback);
            SeismicUI.setupBoundsValidation(magMax, magMax.value, rangeApplyCallback);
            SeismicUI.setupBoundsValidation(depMin, depMin.value, rangeApplyCallback);
            SeismicUI.setupBoundsValidation(depMax, depMax.value, rangeApplyCallback);

             const filterLoader = document.getElementById('filter-loader');

            // Filter inputs trigger on Enter key or clicking the Apply Filters button
            if (is3D) {
                [startInput, endInput, magMin, magMax, depMin, depMax].forEach(input => {
                    if (input) {
                        input.addEventListener('keydown', (e) => {
                            if (e.key === 'Enter') {
                                if ((input === startInput || input === endInput) && !window._userExplicitColorSelection) {
                                    currentColorMode = 'date';
                                    if (colorToggle) colorToggle.textContent = 'Date ▾';
                                }
                                applyFilterWithLoader();
                            }
                        });
                    }
                });
            } else {
                [startInput, endInput, magMin, magMax, depMin, depMax].forEach(input => {
                    if (input) {
                        input.addEventListener('keydown', (e) => {
                            if (e.key === 'Enter') {
                                if ((input === startInput || input === endInput) && !window._userExplicitColorSelection) {
                                    currentColorMode = 'date';
                                    if (colorToggle) colorToggle.textContent = 'Date ▾';
                                }
                                applyFilter();
                            }
                        });
                    }
                });
            }

            function applyFilterWithLoader() {
                if (is3D) {
                    filterLoader.classList.add('show');
                    setTimeout(() => {
                        try { applyFilter(); } catch (e) { console.error('Filter Error:', e); }
                        setTimeout(() => filterLoader.classList.remove('show'), 80);
                    }, 40);
                } else {
                    try { applyFilter(); } catch (e) { console.error('Filter Error:', e); }
                }
            }
            window.applyFilterWithLoader = applyFilterWithLoader;

            const resetBtn = document.getElementById('reset-filters-btn');
            if (resetBtn) {
                resetBtn.onclick = (e) => {
                    e.preventDefault();
                    if (startInput) startInput.value = initialStaticDefaults.startDate;
                    if (endInput) endInput.value = initialStaticDefaults.endDate;
                    if (magMin) magMin.value = initialStaticDefaults.magMin;
                    if (magMax) magMax.value = initialStaticDefaults.magMax;
                    if (depMin) depMin.value = initialStaticDefaults.depMin;
                    if (depMax) depMax.value = initialStaticDefaults.depMax;

                    if (typeof showStatusToast === 'function') {
                        showStatusToast("Filters reset to default values", true);
                    }

                    if (is3D) {
                        applyFilterWithLoader();
                    } else {
                        applyFilter();
                    }
                };
            }

            if (is3D) {
                applyBtn.style.display = 'flex';
                applyBtn.onclick = applyFilterWithLoader;
                // Initial filter run to sync filtered state and vectors
                await applyFilter();
                // Manually trigger initial legend update for 3D
                updateGlassLegend(true, 'Depth (KM)', currentColorScale, invertScale, quakeData.dep_limit || quakeData.dep_range, { startDate: quakeData.start_date });
            } else {
                applyBtn.style.display = 'flex';
                applyBtn.onclick = applyFilter;
                // Initial legend update for 2D view
                await applyFilter();
                updateGlassLegend(
                    currentViewMode !== 'heatmap',
                    currentColorMode === 'dep' ? 'Depth (KM)' : (currentColorMode === 'mag' ? 'Magnitude' : 'Date'),
                    currentColorScale,
                    invertScale,
                    quakeData.dep_limit || quakeData.dep_range,
                    { startDate: quakeData.start_date }
                );
            }

            async function applyFilter() {
                if (invertCheck) invertScale = invertCheck.checked;
                const start = startInput.value ? startInput.value.trim() : '';
                const end = endInput.value ? endInput.value.trim() : '';
                const m1 = parseFloat(magMin.value) || 0, m2 = parseFloat(magMax.value) || 9.9;
                const d1 = parseFloat(depMin.value) || 0, d2 = parseFloat(depMax.value) || 9999;
                const indices = [];

                const N_total = (dates && dates.length > 0) ? dates.length : totalCount;
                for (let i = 0; i < N_total; i++) {
                    const dt = (dates && dates.length > i) ? dates[i] : '';
                    const m = quakeData.magnitude ? quakeData.magnitude[i] : 0;
                    const d = quakeData.depth ? Math.abs(quakeData.depth[i]) : 0;
                    const dateMatch = (!start || !dt || dt >= start) && (!end || !dt || dt <= end);
                    const magMatch = (m >= m1 && m <= m2);
                    const depMatch = (d >= d1 && d <= d2);
                    if (dateMatch && magMatch && depMatch) indices.push(i);
                }

                const allMatch = (indices.length === N_total);
                let filtered;
                if (allMatch) {
                    filtered = {
                        lon: quakeData.longitude,
                        lat: quakeData.latitude,
                        mag: quakeData.magnitude,
                        dep: quakeData.depth,
                        times: quakeData.times,
                        dnum: quakeData.dates_num,
                        hover: quakeData.hover
                    };
                } else {
                    const N = indices.length;
                    const fLon = new Float32Array(N);
                    const fLat = new Float32Array(N);
                    const fMag = new Float32Array(N);
                    const fDep = new Float32Array(N);
                    const fDnum = new Float32Array(N);
                    const fTimes = new Array(N);
                    const fHover = new Array(N);

                    const qLon = quakeData.longitude;
                    const qLat = quakeData.latitude;
                    const qMag = quakeData.magnitude;
                    const qDep = quakeData.depth;
                    const qDnum = quakeData.dates_num;
                    const qTimes = quakeData.times;
                    const qHover = quakeData.hover;
                    const hasHover = qHover && qHover.length === (qMag ? qMag.length : 0);

                    for (let k = 0; k < N; k++) {
                        const i = indices[k];
                        fLon[k] = qLon[i];
                        fLat[k] = qLat[i];
                        fMag[k] = qMag[i];
                        fDep[k] = qDep[i];
                        fDnum[k] = qDnum[i];
                        if (qTimes) fTimes[k] = qTimes[i];
                        fHover[k] = hasHover ? qHover[i] : `Date: ${qTimes ? qTimes[i] : ''}<br>Magnitude: ${qMag[i].toFixed(1)}<br>Depth: ${Math.abs(qDep[i]).toFixed(1)} km`;
                    }

                    filtered = {
                        lon: fLon,
                        lat: fLat,
                        mag: fMag,
                        dep: fDep,
                        times: fTimes,
                        dnum: fDnum,
                        hover: fHover
                    };
                }

                window.currentFilteredData = {
                    longitude: filtered.lon,
                    latitude: filtered.lat,
                    depth: filtered.dep,
                    magnitude: filtered.mag,
                    times: filtered.times
                };
                if (window.quakeData) {
                    window.quakeData.filtered = window.currentFilteredData;
                }

                const isHeatmap = (currentViewMode === 'heatmap');
                const isDep = (currentColorMode === 'dep');
                const isMag = (currentColorMode === 'mag');
                const isDate = (currentColorMode === 'date');

                let limits, colorArr, barTitle;
                if (isDep) {
                    limits = quakeData.dep_limit || quakeData.dep_range || [0, 10];
                    colorArr = filtered.dep;
                    barTitle = 'Depth (KM)';
                } else if (isMag) {
                    limits = quakeData.mag_limit || quakeData.mag_range || [0, 10];
                    colorArr = filtered.mag;
                    barTitle = 'Magnitude';
                } else {
                    let minD = Infinity, maxD = -Infinity;
                    for (let i = 0; i < filtered.dnum.length; i++) {
                        const val = filtered.dnum[i];
                        if (val < minD) minD = val;
                        if (val > maxD) maxD = val;
                    }

                    const getOffset = (dateStr) => {
                        if (!dateStr || !quakeData.start_date) return null;
                        const p1 = String(dateStr).split('-').map(Number);
                        const p2 = String(quakeData.start_date).split('-').map(Number);
                        if (p1.length < 3 || p2.length < 3) return null;
                        const t1 = Date.UTC(p1[0], p1[1] - 1, p1[2]);
                        const t2 = Date.UTC(p2[0], p2[1] - 1, p2[2]);
                        return (t1 - t2) / 86400000;
                    };

                    const sOffset = getOffset(start);
                    const eOffset = getOffset(end);

                    let minVal = (sOffset !== null && !isNaN(sOffset)) ? sOffset : minD;
                    let maxVal = (eOffset !== null && !isNaN(eOffset)) ? eOffset : maxD;

                    if (minVal === Infinity || maxVal === -Infinity) {
                        limits = quakeData.date_limit || quakeData.date_range || [0, 1];
                    } else if (minVal >= maxVal) {
                        limits = [minVal, minVal + 1];
                    } else {
                        limits = [minVal, maxVal];
                    }

                    colorArr = filtered.dnum;
                    barTitle = 'Date';
                }

                const maxMag = filtered.mag.length > 0 ? filtered.mag.reduce((acc, m) => Math.max(acc, m), 0.1) : 1;
                const markerSizes = currentSizeMode === 'magnitude' 
                    ? (is3D ? Array.from(filtered.mag).map(m => Math.max(8, Math.pow(Math.max(0, m), 2) * 1.5))
                            : Array.from(filtered.mag).map(m => Math.max(0.1, m)))
                    : (is3D ? 5 : 6);

                if (is3D) {
                    let depthIdx = -1, dateIdx = -1;
                    for (let i = 0; i < gd.data.length; i++) {
                        const tr = gd.data[i];
                        if (!tr) continue;
                        const name = tr.name || '';
                        if (name === 'Earthquakes (Depth)' || (tr.type === 'scatter3d' && i === 1 && !name.includes('Date') && !name.includes('Stations') && !name.includes('Uplift') && !name.includes('Tomography') && !name.includes('Tomografia'))) {
                            depthIdx = i;
                        } else if (name === 'Earthquakes (Date)' || (tr.type === 'scatter3d' && i === 2 && !name.includes('Depth') && !name.includes('Stations') && !name.includes('Uplift') && !name.includes('Tomography') && !name.includes('Tomografia'))) {
                            dateIdx = i;
                        }
                    }
                    const traceIdx = isDate ? (dateIdx !== -1 ? dateIdx : 2) : (depthIdx !== -1 ? depthIdx : 1);
                    const otherIdx = isDate ? (depthIdx !== -1 ? depthIdx : 1) : (dateIdx !== -1 ? dateIdx : 2);

                    if (otherIdx !== -1 && otherIdx < gd.data.length) {
                        try {
                            const pHide = Plotly.restyle(gd, { visible: [false] }, [otherIdx]);
                            if (pHide && typeof pHide.then === 'function') await pHide;
                        } catch (e) {}
                    }
                    if (traceIdx !== -1 && traceIdx < gd.data.length) {
                        try {
                            const pShow = Plotly.restyle(gd, {
                                x: [filtered.lon], y: [filtered.lat], z: [filtered.dep],
                                'marker.size': [markerSizes],
                                'marker.color': [colorArr],
                                'marker.cmin': [limits[0]],
                                'marker.cmax': [limits[1]],
                                'marker.colorscale': [getPlotlyScale(currentColorScale)],
                                'marker.reversescale': [invertScale],
                                'marker.showscale': [false],
                                hovertext: [filtered.hover],
                                text: [filtered.hover],
                                hovertemplate: ['%{hovertext}<extra></extra>'],
                                hoverinfo: ['text'],
                                visible: [true]
                            }, [traceIdx]);
                            if (pShow && typeof pShow.then === 'function') await pShow;
                        } catch (e) {}
                    }
                } else {
                    let scatterIdx = -1, heatmapIdx = -1;
                    for (let i = 0; i < gd.data.length; i++) {
                        const tr = gd.data[i];
                        if (!tr) continue;
                        const name = tr.name || '';
                        const isDensity = (tr.type === 'densitymapbox' || tr.type === 'densitymap');
                        if (name.includes('Heatmap') || isDensity) {
                            heatmapIdx = i;
                        } else if (name.includes('Earthquakes') || ((tr.type === 'scattermapbox' || tr.type === 'scattermap') && !name.includes('Stations') && !name.includes('Uplift') && !name.includes('Tomography') && !name.includes('Tomografia'))) {
                            scatterIdx = i;
                        }
                    }

                    if (isHeatmap) {
                        if (scatterIdx !== -1) gd.data[scatterIdx].visible = false;
                        if (heatmapIdx !== -1) {
                            gd.data[heatmapIdx].visible = true;
                            gd.data[heatmapIdx].lat = filtered.lat;
                            gd.data[heatmapIdx].lon = filtered.lon;
                            gd.data[heatmapIdx].z = filtered.mag;
                            gd.data[heatmapIdx].hovertext = filtered.hover;
                            gd.data[heatmapIdx].text = filtered.hover;
                            gd.data[heatmapIdx].hovertemplate = '%{hovertext}<extra></extra>';
                            gd.data[heatmapIdx].hoverinfo = 'text';
                            if (gd.data[heatmapIdx].colorscale !== undefined) {
                                gd.data[heatmapIdx].colorscale = getPlotlyScale(currentColorScale);
                                gd.data[heatmapIdx].reversescale = invertScale;
                            }
                        }
                    } else {
                        if (heatmapIdx !== -1) gd.data[heatmapIdx].visible = false;
                        if (scatterIdx !== -1) {
                            gd.data[scatterIdx].visible = true;
                            gd.data[scatterIdx].lat = filtered.lat;
                            gd.data[scatterIdx].lon = filtered.lon;
                            gd.data[scatterIdx].hovertext = filtered.hover;
                            gd.data[scatterIdx].text = filtered.hover;
                            gd.data[scatterIdx].hovertemplate = '%{hovertext}<extra></extra>';
                            gd.data[scatterIdx].hoverinfo = 'text';
                            if (!gd.data[scatterIdx].marker) gd.data[scatterIdx].marker = {};
                            gd.data[scatterIdx].marker.size = markerSizes;
                            gd.data[scatterIdx].marker.color = colorArr;
                            gd.data[scatterIdx].marker.cmin = limits[0];
                            gd.data[scatterIdx].marker.cmax = limits[1];
                            gd.data[scatterIdx].marker.colorscale = getPlotlyScale(currentColorScale);
                            gd.data[scatterIdx].marker.reversescale = invertScale;
                            gd.data[scatterIdx].marker.showscale = false;
                            delete gd.data[scatterIdx].marker.coloraxis;
                            if (currentSizeMode === 'magnitude') {
                                gd.data[scatterIdx].marker.sizemode = 'area';
                                gd.data[scatterIdx].marker.sizeref = maxMag / 400;
                            } else {
                                gd.data[scatterIdx].marker.sizemode = 'diameter';
                                gd.data[scatterIdx].marker.sizeref = 1;
                            }
                        }
                    }
                    try {
                        const pReact = Plotly.react(gd, gd.data, gd.layout);
                        if (pReact && typeof pReact.then === 'function') await pReact;
                    } catch (e) {
                        try { Plotly.redraw(gd); } catch (e2) {}
                    }
                }
                if (is3D && window.SeismicUI && typeof window.SeismicUI.bringMarkersToFront === 'function') {
                    window.SeismicUI.bringMarkersToFront();
                }

                
                currentBarTitle = barTitle;
                currentLimits = limits;

                // Update Glass Legend
                updateGlassLegend(
                    currentViewMode !== 'heatmap',
                    barTitle,
                    currentColorScale,
                    invertScale,
                    limits,
                    { startDate: quakeData.start_date }
                );
            }

            // Finally hide the loader once everything is ready
            hideInitLoader();
        }

        function startInit() {
            initVisualization().catch(err => {
                console.error('Failed to load visualization data:', err);
                if (typeof showStatusToast === 'function') showStatusToast('Failed to load data.');
                hideInitLoader();
            });
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', startInit);
        } else {
            startInit();
        }
