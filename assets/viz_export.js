// --- Seismic Viewer: Modular Export Subsystem (Screenshots, GeoJSON & CSV Exports) ---
(function() {
    'use strict';

    window.SeismicExport = {
        _activeScreenshotDataUrl: null,
        _pendingClusterPayload: null,
        _activeClusterTabIdx: 0,
        _exportFormat: 'csv', // 'csv', 'geojson', or 'json'

        setExportFormat(fmt) {
            this._exportFormat = (fmt === 'geojson' || fmt === 'json') ? fmt : 'csv';
            
            const btnCsv = document.getElementById('fmt-csv-btn');
            const btnGeo = document.getElementById('fmt-geojson-btn');
            const btnJson = document.getElementById('fmt-json-btn');
            
            [
                { btn: btnCsv, id: 'csv' },
                { btn: btnGeo, id: 'geojson' },
                { btn: btnJson, id: 'json' }
            ].forEach(({ btn, id }) => {
                if (!btn) return;
                if (this._exportFormat === id) {
                    btn.classList.add('active');
                    btn.style.background = 'rgba(16,185,129,0.3)';
                    btn.style.color = '#fff';
                    btn.style.border = '1px solid rgba(16,185,129,0.5)';
                } else {
                    btn.classList.remove('active');
                    btn.style.background = 'transparent';
                    btn.style.color = 'rgba(255,255,255,0.65)';
                    btn.style.border = '1px solid transparent';
                }
            });

            this.updateClusterExportButtons();
            this.renderClusterPreviewTable();
        },

        async captureScreenshot() {
            if (window.SeismicUI && typeof window.SeismicUI.toggleExportModal === 'function') {
                window.SeismicUI.toggleExportModal(true);
            }
            const gd = document.querySelector('.plotly-graph-div');
            if (!gd) {
                if (typeof showStatusToast === 'function') showStatusToast('No visualization found to capture', false);
                return;
            }

            const elementsToHide = [
                '#back-btn', '#camera-controls', '#info-btn', '#overlay-btn',
                '#screenshot-btn', '#shortcuts-btn', '#layer-modal', '#export-modal',
                '#shortcuts-modal', '#glass-legend', '#info-panel', '#left-panel-wrapper',
                '#filter-bar', '#ws-status', '.timeline-container', '.playback-controls',
                '#settings-bar', '#swarm-chart-dialog', '#screenshot-preview-dialog', '#cluster-csv-dialog'
            ];

            const hiddenElements = [];
            elementsToHide.forEach(sel => {
                const els = document.querySelectorAll(sel);
                els.forEach(el => {
                    if (el && el.style.visibility !== 'hidden' && getComputedStyle(el).display !== 'none') {
                        el.style.visibility = 'hidden';
                        hiddenElements.push(el);
                    }
                });
            });

            try {
                if (gd._fullLayout) {
                    const mapFull = gd._fullLayout.mapbox || gd._fullLayout.map;
                    if (mapFull) {
                        const mapKey = gd._fullLayout.map ? 'map' : 'mapbox';
                        gd.layout[mapKey] = gd.layout[mapKey] || {};
                        if (mapFull.center) gd.layout[mapKey].center = Object.assign({}, mapFull.center);
                        if (mapFull.zoom !== undefined) gd.layout[mapKey].zoom = mapFull.zoom;
                        if (mapFull.bearing !== undefined) gd.layout[mapKey].bearing = mapFull.bearing;
                        if (mapFull.pitch !== undefined) gd.layout[mapKey].pitch = mapFull.pitch;
                    }
                    if (gd._fullLayout.scene && gd._fullLayout.scene.camera) {
                        gd.layout.scene = gd.layout.scene || {};
                        gd.layout.scene.camera = JSON.parse(JSON.stringify(gd._fullLayout.scene.camera));
                    }
                    if (gd._fullLayout.xaxis && gd._fullLayout.xaxis.range) {
                        gd.layout.xaxis = gd.layout.xaxis || {};
                        gd.layout.xaxis.range = [...gd._fullLayout.xaxis.range];
                    }
                    if (gd._fullLayout.yaxis && gd._fullLayout.yaxis.range) {
                        gd.layout.yaxis = gd.layout.yaxis || {};
                        gd.layout.yaxis.range = [...gd._fullLayout.yaxis.range];
                    }
                }

                const rect = gd.getBoundingClientRect();
                const dataUrl = await Plotly.toImage(gd, {
                    format: 'png',
                    width: Math.round(rect.width || gd.clientWidth || window.innerWidth),
                    height: Math.round(rect.height || gd.clientHeight || window.innerHeight),
                    scale: 2
                });

                this._activeScreenshotDataUrl = dataUrl;
                this.openScreenshotPreview(dataUrl);
            } catch (err) {
                console.error('[Screenshot] Error:', err);
                if (typeof showStatusToast === 'function') showStatusToast('Capture failed: ' + err.message, false);
            } finally {
                hiddenElements.forEach(el => el.style.visibility = 'visible');
            }
        },

        openScreenshotPreview(dataUrl) {
            const previewImg = document.getElementById('screenshot-preview-img');
            const dialog = document.getElementById('screenshot-preview-dialog');
            if (previewImg && dialog) {
                previewImg.src = dataUrl;
                dialog.classList.add('active');
            }
        },

        closeScreenshotPreview() {
            const dialog = document.getElementById('screenshot-preview-dialog');
            if (dialog) dialog.classList.remove('active');
            this._activeScreenshotDataUrl = null;
        },

        async downloadScreenshotPNG() {
            if (!this._activeScreenshotDataUrl) return;
            const link = document.createElement('a');
            link.download = `seismic_view_${new Date().toISOString().replace(/[:.]/g, '-')}.png`;
            link.href = this._activeScreenshotDataUrl;
            link.click();
            if (typeof showStatusToast === 'function') showStatusToast('Screenshot saved successfully', true);
            this.closeScreenshotPreview();
        },

        async exportClustersCSV() {
            if (typeof window.pauseAnimation === 'function') window.pauseAnimation();

            let isClusteringActive = false;
            if (window.IS_CLUSTER_VIEW || window.animClusteringEnabled) isClusteringActive = true;
            else if (window.quakeData && (window.quakeData.cluster || window.quakeData.cluster_indices)) isClusteringActive = true;

            if (!isClusteringActive) {
                if (typeof showStatusToast === 'function') showStatusToast("Clustering is not active in the current view.", false);
                return;
            }

            if (window.SeismicUI && typeof window.SeismicUI.toggleExportModal === 'function') {
                window.SeismicUI.toggleExportModal(true);
            }

            let payload = null;
            if (typeof window.getCurrentFrameClusterExportData === 'function') {
                payload = window.getCurrentFrameClusterExportData();
            }

            if (!payload || !payload.clusters || payload.clusters.length === 0) {
                const qd = window.quakeData || {};
                if (qd.cluster || qd.cluster_indices) {
                    const clustersList = [];
                    const cIndices = qd.cluster_indices || {};
                    const nC = qd.n_clusters || 0;
                    for (let i = 0; i < nC; i++) {
                        const idxs = cIndices[i] || cIndices[String(i)] || [];
                        if (idxs.length > 0) {
                            clustersList.push({
                                name: `Cluster ${i + 1}`,
                                filename: `cluster_${i + 1}.csv`,
                                clusterNum: i + 1,
                                internalLbl: i,
                                indices: idxs
                            });
                        }
                    }
                    const outlierIdxs = cIndices[-1] || cIndices['-1'] || [];
                    if (outlierIdxs.length > 0) {
                        clustersList.push({
                            name: "Outliers",
                            filename: "outliers.csv",
                            clusterNum: -1,
                            internalLbl: -1,
                            indices: outlierIdxs
                        });
                    }
                    if (clustersList.length > 0) {
                        payload = {
                            method: qd.clustering_method || 'dbscan',
                            params: qd.clustering_params || {},
                            clusters: clustersList
                        };
                    }
                }
            }

            if (!payload || !payload.clusters || payload.clusters.length === 0) {
                if (typeof showStatusToast === 'function') showStatusToast("No clusters found in the current frame.", false);
                return;
            }

            this.openClusterCsvPreview(payload);
        },

        openClusterCsvPreview(payload) {
            const clusters = payload.clusters || [];
            if (clusters.length === 0) {
                if (typeof showStatusToast === 'function') showStatusToast("No cluster data available.", false);
                return;
            }

            this._pendingClusterPayload = payload;
            this._activeClusterTabIdx = 0;

            const tabsBar = document.getElementById('cluster-csv-nav');
            if (tabsBar) {
                tabsBar.innerHTML = '';
                clusters.forEach((c, idx) => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    const count = (c.indices || []).length;
                    btn.className = 'cluster-csv-tab' + (idx === this._activeClusterTabIdx ? ' active' : '');
                    btn.textContent = `${c.name} (${count})`;
                    btn.onclick = () => this.selectClusterPreviewTab(idx);
                    tabsBar.appendChild(btn);
                });
            }

            this.renderClusterPreviewTable();
            this.updateClusterExportButtons();

            const dialog = document.getElementById('cluster-csv-dialog');
            if (dialog) dialog.classList.add('active');
        },

        selectClusterPreviewTab(idx) {
            this._activeClusterTabIdx = idx;
            const tabsBar = document.getElementById('cluster-csv-nav');
            if (tabsBar) {
                const tabs = tabsBar.querySelectorAll('.cluster-csv-tab');
                tabs.forEach((tab, i) => {
                    tab.classList.toggle('active', i === idx);
                });
            }
            this.renderClusterPreviewTable();
            this.updateClusterExportButtons();
        },

        updateClusterExportButtons() {
            if (!this._pendingClusterPayload || !this._pendingClusterPayload.clusters) return;
            const clusters = this._pendingClusterPayload.clusters;
            const currentCluster = clusters[this._activeClusterTabIdx];
            const selLabel = document.getElementById('btn-download-selected-label');
            const ext = this._exportFormat === 'geojson' ? '.geojson' : (this._exportFormat === 'json' ? '.json' : '.csv');

            if (selLabel && currentCluster) {
                const baseName = (currentCluster.name || `cluster_${this._activeClusterTabIdx + 1}`).toLowerCase().replace(/\s+/g, '_');
                selLabel.textContent = `Download ${baseName}${ext}`;
            }
            const zipLabel = document.getElementById('btn-download-zip-label');
            if (zipLabel) {
                zipLabel.textContent = `Download All (${clusters.length} ${ext} in .zip)`;
            }
        },

        renderClusterPreviewTable() {
            if (!this._pendingClusterPayload || !this._pendingClusterPayload.clusters) return;
            const clusters = this._pendingClusterPayload.clusters;
            const currentCluster = clusters[this._activeClusterTabIdx];
            if (!currentCluster) return;

            const qd = window.quakeData || window.fullData || {};
            const times = qd.times || [];
            const lats = qd.lat || qd.latitude || [];
            const lons = qd.lon || qd.longitude || [];
            const deps = qd.dep || qd.depth || [];
            const mags = qd.mag || qd.magnitude || [];
            const indices = currentCluster.indices || [];

            const metaEl = document.getElementById('cluster-csv-meta');
            const ext = this._exportFormat === 'geojson' ? '.geojson' : (this._exportFormat === 'json' ? '.json' : '.csv');
            const baseName = (currentCluster.name || `cluster_${this._activeClusterTabIdx + 1}`).toLowerCase().replace(/\s+/g, '_');

            if (metaEl) {
                const method = (this._pendingClusterPayload.method || 'DBSCAN').toUpperCase();
                metaEl.textContent = `Target: ${baseName}${ext} • Format: ${this._exportFormat.toUpperCase()} • Algorithm: ${method}`;
            }

            const badgeEl = document.getElementById('cluster-csv-count-badge');
            if (badgeEl) {
                badgeEl.textContent = indices.length > 100 
                    ? `Previewing 100 of ${indices.length} events` 
                    : `Total events: ${indices.length}`;
            }

            const tbody = document.getElementById('cluster-csv-tbody');
            if (!tbody) return;
            tbody.innerHTML = '';

            const maxRows = Math.min(indices.length, 100);
            for (let r = 0; r < maxRows; r++) {
                const idx = indices[r];
                const tr = document.createElement('tr');

                const tdIdx = document.createElement('td');
                tdIdx.textContent = r + 1;
                tdIdx.style.color = '#64748b';
                tr.appendChild(tdIdx);

                const tdTime = document.createElement('td');
                tdTime.textContent = (times && times[idx] !== undefined) ? String(times[idx]) : '';
                tr.appendChild(tdTime);

                const tdLat = document.createElement('td');
                tdLat.textContent = (lats && lats[idx] !== undefined) ? Number(lats[idx]).toFixed(4) : '';
                tr.appendChild(tdLat);

                const tdLon = document.createElement('td');
                tdLon.textContent = (lons && lons[idx] !== undefined) ? Number(lons[idx]).toFixed(4) : '';
                tr.appendChild(tdLon);

                const tdDep = document.createElement('td');
                tdDep.textContent = (deps && deps[idx] !== undefined) ? Math.abs(Number(deps[idx])).toFixed(2) : '';
                tr.appendChild(tdDep);

                const tdMag = document.createElement('td');
                tdMag.textContent = (mags && mags[idx] !== undefined) ? Number(mags[idx]).toFixed(1) : '';
                tr.appendChild(tdMag);

                tbody.appendChild(tr);
            }
        },

        closeClusterCsvDialog() {
            const dialog = document.getElementById('cluster-csv-dialog');
            if (dialog) dialog.classList.remove('active');
        },

        async downloadSelectedClusterCSV() {
            if (!this._pendingClusterPayload || !this._pendingClusterPayload.clusters) {
                if (typeof showStatusToast === 'function') showStatusToast("No cluster data to export.", false);
                return;
            }
            const currentCluster = this._pendingClusterPayload.clusters[this._activeClusterTabIdx];
            if (!currentCluster) {
                if (typeof showStatusToast === 'function') showStatusToast("Selected cluster not found.", false);
                return;
            }
            if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.export_single_cluster_csv) {
                if (typeof showStatusToast === 'function') showStatusToast("Export API not available.", false);
                return;
            }
            try {
                const ext = this._exportFormat === 'geojson' ? '.geojson' : (this._exportFormat === 'json' ? '.json' : '.csv');
                const baseName = (currentCluster.name || `cluster_${this._activeClusterTabIdx + 1}`).toLowerCase().replace(/\s+/g, '_');
                const payload = {
                    filename: `${baseName}${ext}`,
                    indices: currentCluster.indices,
                    method: this._pendingClusterPayload.method,
                    params: this._pendingClusterPayload.params,
                    format: this._exportFormat
                };
                const res = await window.pywebview.api.export_single_cluster_csv(payload);
                if (res && res.status === 'success') {
                    if (typeof showStatusToast === 'function') showStatusToast(`Saved ${res.filename} (${this._exportFormat.toUpperCase()}) successfully!`, true, 4000);
                    this.closeClusterCsvDialog();
                } else if (res && res.status === 'cancelled') {
                    if (typeof showStatusToast === 'function') showStatusToast("Export cancelled.", true);
                } else {
                    if (typeof showStatusToast === 'function') showStatusToast("Error: " + (res ? res.message : "Unknown error"), false);
                }
            } catch (err) {
                console.error("Export failed:", err);
                if (typeof showStatusToast === 'function') showStatusToast("Export failed: " + err, false);
            }
        },

        async downloadAllClustersZIP() {
            if (!this._pendingClusterPayload || !this._pendingClusterPayload.clusters) {
                if (typeof showStatusToast === 'function') showStatusToast("No cluster data to export.", false);
                return;
            }
            if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.export_clusters_zip) {
                if (typeof showStatusToast === 'function') showStatusToast("ZIP Export API not available.", false);
                return;
            }
            try {
                const payload = Object.assign({}, this._pendingClusterPayload, {
                    format: this._exportFormat
                });
                const res = await window.pywebview.api.export_clusters_zip(payload);
                if (res && res.status === 'success') {
                    if (typeof showStatusToast === 'function') showStatusToast(`Exported all ${res.count} clusters (${this._exportFormat.toUpperCase()}) to ZIP archive successfully!`, true, 4000);
                    this.closeClusterCsvDialog();
                } else if (res && res.status === 'cancelled') {
                    if (typeof showStatusToast === 'function') showStatusToast("Export cancelled.", true);
                } else {
                    if (typeof showStatusToast === 'function') showStatusToast("Error: " + (res ? res.message : "Unknown error"), false);
                }
            } catch (err) {
                console.error("ZIP export failed:", err);
                if (typeof showStatusToast === 'function') showStatusToast("ZIP export failed: " + err, false);
            }
        }
    };

    // Integrate with window.SeismicUI if already defined or once defined
    function bridgeToSeismicUI() {
        if (!window.SeismicUI) window.SeismicUI = {};
        for (const [key, fn] of Object.entries(window.SeismicExport)) {
            if (typeof fn === 'function') {
                window.SeismicUI[key] = fn.bind(window.SeismicExport);
            }
        }
    }
    bridgeToSeismicUI();
    window.addEventListener('DOMContentLoaded', bridgeToSeismicUI);
})();
