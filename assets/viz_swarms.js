// --- Seismic Viewer: Modular Swarms Subsystem (Swarm Charts, Timeline Canvas & Dialogs) ---
(function() {
    'use strict';

    function parseSwarmUtcDate(timeStr) {
        if (!timeStr) return null;
        if (timeStr instanceof Date) return isNaN(timeStr.getTime()) ? null : timeStr;
        let s = String(timeStr).trim();
        if (!s) return null;
        if (!s.includes('T') && s.includes(' ')) {
            s = s.replace(' ', 'T');
        }
        if (!s.endsWith('Z') && !s.includes('+') && !/[0-9]-[0-9]{2}:/.test(s)) {
            s += 'Z';
        }
        const d = new Date(s);
        return isNaN(d.getTime()) ? null : d;
    }

    const SeismicSwarms = {
        _activeSwarmChartDataUrl: null,
        _activeSwarmChartFilename: 'seismic_swarm_magnitude_vs_time.png',
        _currentChartSwarmIdx: 0,

        openSwarmChartDialog(swarmIndex) {
            if (window.SeismicUI && typeof window.SeismicUI.toggleExportModal === 'function') {
                window.SeismicUI.toggleExportModal(true);
            }

            const qd = window.quakeData || {};
            const swarms = (qd.swarms && qd.swarms.length > 0) ? qd.swarms : (window.swarmsList || []);

            if (!swarms || swarms.length === 0) {
                if (typeof showStatusToast === 'function') {
                    showStatusToast("Nessuno sciame sismico rilevato nel dataset.", false);
                }
                return;
            }

            let sIdx = (typeof swarmIndex === 'number') ? swarmIndex : (typeof window.currentSwarmIdx === 'number' ? window.currentSwarmIdx : this._currentChartSwarmIdx || 0);
            if (sIdx < 0) sIdx = 0;
            if (sIdx >= swarms.length) sIdx = swarms.length - 1;
            this._currentChartSwarmIdx = sIdx;

            const swarm = swarms[sIdx];
            if (!swarm || !swarm.indices || swarm.indices.length === 0) {
                if (typeof showStatusToast === 'function') {
                    showStatusToast("Dati dello sciame non validi per la visualizzazione.", false);
                }
                return;
            }

            // Collect swarm earthquakes respecting current filters (on screen)
            const allDeps = qd.dep || qd.depth || [];
            const allMags = qd.mag || qd.magnitude || [];
            const allTimes = qd.times || [];

            const magMin = typeof window.appliedMagMin === 'number' ? window.appliedMagMin : -10;
            const magMax = typeof window.appliedMagMax === 'number' ? window.appliedMagMax : 10;
            const depMin = typeof window.appliedDepMin === 'number' ? window.appliedDepMin : -100;
            const depMax = typeof window.appliedDepMax === 'number' ? window.appliedDepMax : 1000;

            const allEvents = [];
            const filteredEvents = [];

            for (let k = 0; k < swarm.indices.length; k++) {
                const idx = swarm.indices[k];
                const mag = (allMags && allMags[idx] !== undefined) ? allMags[idx] : (swarm.mags ? swarm.mags[k] : 0);
                const timeStr = (allTimes && allTimes[idx] !== undefined) ? allTimes[idx] : (swarm.times ? swarm.times[k] : '');
                const rawDep = (allDeps && allDeps[idx] !== undefined) ? allDeps[idx] : 0;
                const posDep = Math.abs(rawDep);

                const dt = parseSwarmUtcDate(timeStr);
                const timestamp = dt ? dt.getTime() : (k * 1000);

                const ev = {
                    idx: idx,
                    k: k,
                    mag: Number(mag),
                    timeStr: timeStr,
                    timestamp: timestamp
                };

                allEvents.push(ev);

                // Filter check: magnitude and depth on screen
                if (mag >= magMin && mag <= magMax && posDep >= depMin && posDep <= depMax) {
                    filteredEvents.push(ev);
                }
            }

            let events = filteredEvents;
            if (events.length === 0) {
                // If filter settings excluded all swarm events, fallback to all events in swarm
                events = allEvents;
            }

            if (events.length === 0) {
                if (typeof showStatusToast === 'function') {
                    showStatusToast("Nessun terremoto trovato per questo sciame.", false);
                }
                return;
            }

            // Ensure chronological order
            events.sort((a, b) => a.timestamp - b.timestamp);

            // Render chart canvas
            const canvas = this.generateSwarmChartCanvas(swarm, events);
            const dataUrl = canvas.toDataURL('image/png');
            this._activeSwarmChartDataUrl = dataUrl;

            const swarmId = swarm.id || (sIdx + 1);
            this._activeSwarmChartFilename = `swarm_${swarmId}_magnitude_vs_time.png`;

            // Update modal UI elements
            const titleEl = document.getElementById('swarm-chart-dialog-title');
            if (titleEl) {
                titleEl.textContent = `Swarm ${swarmId} — Magnitude vs. Time`;
            }
            const subEl = document.getElementById('swarm-chart-dialog-sub');
            if (subEl) {
                subEl.textContent = `${events.length} of ${swarm.event_count} events on screen • Max Md ${swarm.max_mag.toFixed(1)}`;
            }
            const counterEl = document.getElementById('modal-swarm-counter');
            const navEl = document.getElementById('modal-swarm-nav');
            if (counterEl && navEl) {
                if (swarms.length > 1) {
                    navEl.style.display = 'flex';
                    counterEl.textContent = `Swarm ${sIdx + 1} / ${swarms.length}`;
                } else {
                    navEl.style.display = 'none';
                }
            }
            const imgEl = document.getElementById('swarm-chart-preview-img');
            if (imgEl) {
                imgEl.src = dataUrl;
            }

            const dialog = document.getElementById('swarm-chart-dialog');
            if (dialog) {
                dialog.classList.add('active');
            }
        },

        navigateSwarmChart(direction) {
            const qd = window.quakeData || {};
            const swarms = (qd.swarms && qd.swarms.length > 0) ? qd.swarms : (window.swarmsList || []);
            if (!swarms || swarms.length <= 1) return;

            const curr = typeof this._currentChartSwarmIdx === 'number' ? this._currentChartSwarmIdx : 0;
            let next = curr + direction;
            if (next < 0) next = swarms.length - 1;
            if (next >= swarms.length) next = 0;

            this.openSwarmChartDialog(next);
        },

        closeSwarmChartDialog() {
            const dialog = document.getElementById('swarm-chart-dialog');
            if (dialog) {
                dialog.classList.remove('active');
            }
        },

        async downloadSwarmChart() {
            const dataUrl = this._activeSwarmChartDataUrl || SeismicSwarms._activeSwarmChartDataUrl;
            if (!dataUrl) {
                if (typeof showStatusToast === 'function') showStatusToast("Nessun grafico disponibile da scaricare.", false);
                return;
            }
            const filename = this._activeSwarmChartFilename || SeismicSwarms._activeSwarmChartFilename || 'swarm_magnitude_vs_time.png';

            const api = (typeof getBridgeApi === 'function' ? getBridgeApi() : null) ||
                        (window.pywebview && window.pywebview.api) ||
                        (window.parent && window.parent.pywebview && window.parent.pywebview.api);

            if (api && typeof api.save_screenshot === 'function') {
                try {
                    const result = await api.save_screenshot(dataUrl, filename);
                    if (result && result.status === 'success') {
                        if (typeof showStatusToast === 'function') {
                            showStatusToast('Swarm chart saved: ' + (result.path ? result.path.split(/[/\\]/).pop() : filename), true);
                        }
                        this.closeSwarmChartDialog();
                    } else if (result && result.status === 'cancelled') {
                        if (typeof showStatusToast === 'function') showStatusToast('Download cancelled.', true);
                    } else if (result && result.error) {
                        if (typeof showStatusToast === 'function') showStatusToast('Save failed: ' + result.error, false);
                    }
                } catch (err) {
                    console.error('[SwarmChart] Pywebview save failed:', err);
                    if (typeof showStatusToast === 'function') showStatusToast('Save failed: ' + err.message, false);
                }
            } else {
                this._fallbackBrowserDownload(dataUrl, filename);
                this.closeSwarmChartDialog();
            }
        },

        _fallbackBrowserDownload(dataUrl, filename) {
            const a = document.createElement('a');
            a.href = dataUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            if (typeof showStatusToast === 'function') {
                showStatusToast('Swarm chart downloaded: ' + filename, true);
            }
        },

        _drawRoundRect(ctx, x, y, w, h, r) {
            if (typeof ctx.roundRect === 'function') {
                ctx.beginPath();
                ctx.roundRect(x, y, w, h, r);
            } else {
                ctx.beginPath();
                ctx.moveTo(x + r, y);
                ctx.lineTo(x + w - r, y);
                ctx.quadraticCurveTo(x + w, y, x + w, y + r);
                ctx.lineTo(x + w, y + h - r);
                ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
                ctx.lineTo(x + r, y + h);
                ctx.quadraticCurveTo(x, y + h, x, y + h - r);
                ctx.lineTo(x, y + r);
                ctx.quadraticCurveTo(x, y, x + r, y);
                ctx.closePath();
            }
        },

        _drawStar(ctx, cx, cy, spikes, outerRadius, innerRadius, fillStyle, strokeStyle, lineWidth = 2) {
            let rot = (Math.PI / 2) * 3;
            let x = cx;
            let y = cy;
            const step = Math.PI / spikes;

            ctx.beginPath();
            ctx.moveTo(cx, cy - outerRadius);
            for (let i = 0; i < spikes; i++) {
                x = cx + Math.cos(rot) * outerRadius;
                y = cy + Math.sin(rot) * outerRadius;
                ctx.lineTo(x, y);
                rot += step;

                x = cx + Math.cos(rot) * innerRadius;
                y = cy + Math.sin(rot) * innerRadius;
                ctx.lineTo(x, y);
                rot += step;
            }
            ctx.lineTo(cx, cy - outerRadius);
            ctx.closePath();

            if (fillStyle) {
                ctx.fillStyle = fillStyle;
                ctx.fill();
            }
            if (strokeStyle) {
                ctx.strokeStyle = strokeStyle;
                ctx.lineWidth = lineWidth;
                ctx.stroke();
            }
        },

        generateSwarmChartCanvas(swarm, events) {
            const canvas = document.createElement('canvas');
            canvas.width = 1400;
            canvas.height = 800;
            const ctx = canvas.getContext('2d');

            // 1. Clean White Background
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            // Margins & Plot Area
            const marginLeft = 95;
            const marginRight = 55;
            const marginTop = 90;
            const marginBottom = 85;
            const plotW = canvas.width - marginLeft - marginRight;
            const plotH = canvas.height - marginTop - marginBottom;

            // Plot background box
            ctx.fillStyle = '#fafbfc';
            ctx.fillRect(marginLeft, marginTop, plotW, plotH);
            ctx.strokeStyle = '#cbd5e1';
            ctx.lineWidth = 1.5;
            ctx.strokeRect(marginLeft, marginTop, plotW, plotH);

            // Find Time & Magnitude ranges
            let minT = Infinity, maxT = -Infinity;
            let minM = Infinity, maxM = -Infinity;
            let maxEvent = events[0];

            for (let i = 0; i < events.length; i++) {
                const ev = events[i];
                if (ev.timestamp < minT) minT = ev.timestamp;
                if (ev.timestamp > maxT) maxT = ev.timestamp;
                if (ev.mag < minM) minM = ev.mag;
                if (ev.mag > maxM) {
                    maxM = ev.mag;
                    maxEvent = ev;
                }
            }

            // Buffer time bounds
            let spanT = maxT - minT;
            if (spanT <= 0) {
                minT -= 30000;
                maxT += 30000;
                spanT = 60000;
            } else {
                minT -= spanT * 0.05;
                maxT += spanT * 0.05;
                spanT = maxT - minT;
            }

            // Buffer magnitude bounds
            let yMin = Math.floor(Math.min(0, minM - 0.2) * 2) / 2;
            let yMax = Math.ceil((maxM + 0.6) * 2) / 2;
            if (yMax <= yMin) {
                yMax = yMin + 1.0;
            }

            function getX(t) {
                return marginLeft + ((t - minT) / (spanT || 1)) * plotW;
            }
            function getY(m) {
                return marginTop + plotH - ((m - yMin) / ((yMax - yMin) || 1)) * plotH;
            }

            // 2. Gridlines and Y-Axis ticks
            ctx.textAlign = 'right';
            ctx.textBaseline = 'middle';
            ctx.font = '12px Inter, system-ui, -apple-system, sans-serif';

            const yStep = (yMax - yMin <= 4) ? 0.5 : 1.0;
            for (let m = yMin; m <= yMax + 0.001; m += yStep) {
                const y = getY(m);
                if (y < marginTop || y > marginTop + plotH) continue;

                ctx.strokeStyle = (Math.abs(m) < 0.001) ? '#94a3b8' : '#e2e8f0';
                ctx.lineWidth = (Math.abs(m) < 0.001) ? 1.5 : 1;
                ctx.beginPath();
                ctx.moveTo(marginLeft, y);
                ctx.lineTo(marginLeft + plotW, y);
                ctx.stroke();

                ctx.fillStyle = '#475569';
                ctx.fillText(m.toFixed(1), marginLeft - 12, y);
            }

            // 3. X-Axis ticks (Time)
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            const numXTicks = 7;
            for (let i = 0; i <= numXTicks; i++) {
                const t = minT + (i / numXTicks) * (maxT - minT);
                const x = getX(t);
                const d = new Date(t);

                // Gridline
                ctx.strokeStyle = '#e2e8f0';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(x, marginTop);
                ctx.lineTo(x, marginTop + plotH);
                ctx.stroke();

                // Format Time and Date
                const pad = (n) => String(n).padStart(2, '0');
                const timeStr = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
                const dateStr = `${pad(d.getUTCDate())}/${pad(d.getUTCMonth() + 1)}`;

                ctx.fillStyle = '#1e293b';
                ctx.fillText(timeStr, x, marginTop + plotH + 10);
                ctx.fillStyle = '#64748b';
                ctx.fillText(dateStr, x, marginTop + plotH + 26);
            }

            // 4. Axis Titles
            ctx.save();
            ctx.translate(28, marginTop + plotH / 2);
            ctx.rotate(-Math.PI / 2);
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.font = '700 15px Inter, system-ui, -apple-system, sans-serif';
            ctx.fillStyle = '#0f172a';
            ctx.fillText('Magnitude (Md)', 0, 0);
            ctx.restore();

            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            ctx.font = '700 14px Inter, system-ui, -apple-system, sans-serif';
            ctx.fillStyle = '#0f172a';
            ctx.fillText('Time (UTC)', marginLeft + plotW / 2, canvas.height - 12);

            // 5. Chart Header / Titles
            const swarmId = swarm.id || (typeof window.currentSwarmIdx === 'number' ? window.currentSwarmIdx + 1 : 1);
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';
            ctx.font = '700 22px Inter, system-ui, -apple-system, sans-serif';
            ctx.fillStyle = '#0f172a';
            ctx.fillText(`Seismic Swarm #${swarmId} — Magnitude vs. Time`, marginLeft, 40);

            ctx.font = '13px Inter, system-ui, -apple-system, sans-serif';
            ctx.fillStyle = '#64748b';
            ctx.fillText(`Duration: ${swarm.start_time || ''} → ${swarm.end_time || ''}  •  Events on Screen: ${events.length} / ${swarm.event_count}`, marginLeft, 66);

            // 6. Legend Top Right
            const legendW = 320;
            const legendH = 34;
            const legendX = marginLeft + plotW - legendW;
            const legendY = marginTop - 46;

            ctx.fillStyle = '#ffffff';
            ctx.strokeStyle = '#cbd5e1';
            ctx.lineWidth = 1;
            this._drawRoundRect(ctx, legendX, legendY, legendW, legendH, 6);
            ctx.fill();
            ctx.stroke();

            // Light-blue circle legend item
            ctx.fillStyle = '#38bdf8';
            ctx.beginPath();
            ctx.arc(legendX + 22, legendY + 17, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#0284c7';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';
            ctx.font = '12px Inter, system-ui, -apple-system, sans-serif';
            ctx.fillStyle = '#334155';
            ctx.fillText('Swarm Events', legendX + 35, legendY + 17);

            // Red star legend item
            this._drawStar(ctx, legendX + 155, legendY + 17, 5, 8, 3.5, '#ef4444', '#dc2626', 1.5);
            ctx.fillStyle = '#334155';
            ctx.fillText(`Max Md (★ ${maxEvent.mag.toFixed(1)})`, legendX + 172, legendY + 17);

            // 7. Plot Earthquakes: Light-blue points for all except maxEvent
            for (let i = 0; i < events.length; i++) {
                const ev = events[i];
                if (ev === maxEvent) continue;

                const px = getX(ev.timestamp);
                const py = getY(ev.mag);

                // Subtle vertical drop line to base
                ctx.strokeStyle = 'rgba(56, 189, 248, 0.25)';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(px, getY(yMin));
                ctx.lineTo(px, py);
                ctx.stroke();

                // Outer halo
                ctx.fillStyle = 'rgba(56, 189, 248, 0.2)';
                ctx.beginPath();
                ctx.arc(px, py, 8, 0, Math.PI * 2);
                ctx.fill();

                // Core point
                ctx.fillStyle = '#38bdf8';
                ctx.beginPath();
                ctx.arc(px, py, 5.5, 0, Math.PI * 2);
                ctx.fill();
                ctx.strokeStyle = '#0284c7';
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }

            // 8. Plot Mainshock / Max Magnitude Event: Red Star
            if (maxEvent) {
                const starX = getX(maxEvent.timestamp);
                const starY = getY(maxEvent.mag);

                // Vertical accent guide line
                ctx.strokeStyle = 'rgba(239, 68, 68, 0.5)';
                ctx.lineWidth = 1.5;
                ctx.setLineDash([4, 4]);
                ctx.beginPath();
                ctx.moveTo(starX, getY(yMin));
                ctx.lineTo(starX, starY);
                ctx.stroke();
                ctx.setLineDash([]);

                // Glowing aura around star
                const starGlow = ctx.createRadialGradient(starX, starY, 4, starX, starY, 26);
                starGlow.addColorStop(0, 'rgba(239, 68, 68, 0.35)');
                starGlow.addColorStop(1, 'rgba(239, 68, 68, 0)');
                ctx.fillStyle = starGlow;
                ctx.beginPath();
                ctx.arc(starX, starY, 26, 0, Math.PI * 2);
                ctx.fill();

                // 5-pointed Red Star (outer radius 16, inner radius 7)
                this._drawStar(ctx, starX, starY, 5, 16, 7, '#ef4444', '#b91c1c', 2);

                // Label tag for Max Event
                const badgeText = `★ Max Md ${maxEvent.mag.toFixed(1)}`;
                ctx.font = '700 11px Inter, system-ui, -apple-system, sans-serif';
                const textWidth = ctx.measureText(badgeText).width;
                const badgeW = textWidth + 14;
                const badgeH = 22;
                let badgeX = starX - badgeW / 2;
                let badgeY = starY - 30;

                // Keep badge inside plot bounds
                if (badgeX < marginLeft + 4) badgeX = marginLeft + 4;
                if (badgeX + badgeW > marginLeft + plotW - 4) badgeX = marginLeft + plotW - badgeW - 4;
                if (badgeY < marginTop + 4) badgeY = starY + 18;

                ctx.fillStyle = '#ef4444';
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 1;
                this._drawRoundRect(ctx, badgeX, badgeY, badgeW, badgeH, 4);
                ctx.fill();
                ctx.stroke();

                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = '#ffffff';
                ctx.fillText(badgeText, badgeX + badgeW / 2, badgeY + badgeH / 2);
            }

            return canvas;
        }
    };

    window.SeismicSwarms = SeismicSwarms;
    window.SeismicUI = Object.assign(window.SeismicUI || {}, SeismicSwarms);
})();
