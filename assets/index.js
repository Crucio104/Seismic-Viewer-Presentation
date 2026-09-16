// --- Mouse Parallax Ambient Background (Throttled via requestAnimationFrame) ---
(function() {
    let orb1 = null;
    let orb2 = null;
    let mouseX = 0;
    let mouseY = 0;
    let rafPending = false;

    function updateOrbs() {
        if (!orb1 || !orb2) {
            orb1 = document.querySelector('.orb-1');
            orb2 = document.querySelector('.orb-2');
        }
        if (orb1 && orb2) {
            const x = (mouseX / window.innerWidth - 0.5) * 35;
            const y = (mouseY / window.innerHeight - 0.5) * 35;
            orb1.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
            orb2.style.transform = `translate(${(-x).toFixed(1)}px, ${(-y).toFixed(1)}px)`;
        }
        rafPending = false;
    }

    window.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
        if (!rafPending) {
            rafPending = true;
            requestAnimationFrame(updateOrbs);
        }
    }, { passive: true });
})();

    // --- Custom Dropdown Logic ---
    function toggleDropdown(event, menuId) {
        event.stopPropagation();
        const menu = document.getElementById(menuId);
        const allMenus = document.querySelectorAll('.glass-menu');
        allMenus.forEach(m => {
            if (m.id !== menuId) m.classList.remove('show');
        });
        menu.classList.toggle('show');
    }

    function selectOption(hiddenId, value, label, toggleId, menuId) {
        document.getElementById(hiddenId).value = value;
        document.getElementById(toggleId).textContent = label;
        
        // Update active state
        const menu = document.getElementById(menuId);
        const items = menu.querySelectorAll('.menu-item');
        items.forEach(item => {
            if (item.textContent === label) item.classList.add('active');
            else item.classList.remove('active');
        });
        
        menu.classList.remove('show');
    }

    function stepValue(id, amount) {
        const input = document.getElementById(id);
        const val = parseFloat(input.value) || 0;
        input.value = (val + amount).toFixed(1);
        input.dispatchEvent(new Event('change'));
    }

    // Close dropdowns on outside click
    window.addEventListener('click', () => {
        document.querySelectorAll('.glass-menu').forEach(m => m.classList.remove('show'));
    });

    // --- Message Synchronization ---
    function updateProgress(msg) {
        // Update the overlay message used during heavy operations
        const overlayMsg = document.getElementById('overlay-msg');
        if (overlayMsg) overlayMsg.textContent = msg;
        
        // Update the file picker loader if visible
        const pickerLoaderText = document.querySelector('#loader p');
        if (pickerLoaderText) pickerLoaderText.textContent = msg;
    }

    // --- View Switching Logic ---
    function showFilePicker() {
        document.getElementById('view-hub').classList.remove('active');
        document.getElementById('view-picker').classList.add('active');
        const scModal = document.getElementById('hub-shortcuts-modal');
        if (scModal) scModal.classList.remove('active');
        
        // Reset picker states
         const btn = document.getElementById('pick-btn');
         const status = document.getElementById('status');
         const card = document.getElementById('file-card');
         const loader = document.getElementById('loader');
         btn.disabled = false;
         status.innerHTML = '';
         card.style.display = 'none';
         loader.style.display = 'none';
    }

    function animateCounter(el, target, duration = 700) {
        if (!el) return;
        const startTime = performance.now();
        const endVal = typeof target === 'number' ? target : parseInt(String(target).replace(/[^0-9]/g, ''), 10) || 0;
        if (endVal === 0) {
            el.textContent = '0';
            return;
        }
        function step(now) {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const ease = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(endVal * ease);
            el.textContent = current.toLocaleString();
            if (progress < 1) {
                requestAnimationFrame(step);
            } else {
                el.textContent = endVal.toLocaleString();
            }
        }
        requestAnimationFrame(step);
    }

    function showHub(badgeText, totalDays, swarmsCount, eventCount) {
        let cleanName = badgeText;
        let detectedEvents = eventCount;

        if (badgeText) {
            if (badgeText.includes(' | ')) {
                const parts = badgeText.split(' | ');
                cleanName = parts[0];
                if (detectedEvents === undefined && parts[1]) {
                    const parsed = parseInt(parts[1].replace(/[^0-9]/g, ''), 10);
                    if (!isNaN(parsed)) detectedEvents = parsed;
                }
            }
            document.getElementById('badge-text').textContent = cleanName;
            localStorage.setItem('hub_badge', cleanName);
        }

        if (detectedEvents !== undefined && detectedEvents !== null) {
            window.currentDatasetEventCount = detectedEvents;
            localStorage.setItem('hub_event_count', detectedEvents);
            animateCounter(document.getElementById('chip-events-val'), detectedEvents);
        } else {
            const cachedEvents = localStorage.getItem('hub_event_count');
            if (cachedEvents) {
                animateCounter(document.getElementById('chip-events-val'), parseInt(cachedEvents, 10));
            }
        }

        if (totalDays !== undefined && totalDays !== null) {
            window.currentDatasetTotalDays = totalDays;
            localStorage.setItem('hub_total_days', totalDays);
            animateCounter(document.getElementById('chip-days-val'), totalDays);
        } else {
            const cachedDays = localStorage.getItem('hub_total_days');
            if (cachedDays) {
                animateCounter(document.getElementById('chip-days-val'), parseInt(cachedDays, 10));
            }
        }

        if (swarmsCount !== undefined && swarmsCount !== null) {
            window.currentDatasetSwarmsCount = swarmsCount;
            localStorage.setItem('hub_swarms_count', swarmsCount);
            updateSwarmOptionState(swarmsCount);
            animateCounter(document.getElementById('chip-swarms-val'), swarmsCount);
        } else {
            const cachedSwarms = localStorage.getItem('hub_swarms_count');
            if (cachedSwarms) {
                const s = parseInt(cachedSwarms, 10);
                updateSwarmOptionState(s);
                animateCounter(document.getElementById('chip-swarms-val'), s);
            }
        }

        document.getElementById('view-picker').classList.remove('active');
        document.getElementById('view-hub').classList.add('active');
    }

    function updateSwarmOptionState(count) {
        const swarmRadio = document.getElementById('anim-mode-swarm');
        const swarmLabel = document.getElementById('swarm-radio-label');
        const swarmBadge = document.getElementById('swarm-badge');
        if (!swarmRadio || !swarmLabel || !swarmBadge) return;

        const num = typeof count === 'number' ? count : (window.currentDatasetSwarmsCount ?? 0);
        window.currentDatasetSwarmsCount = num;

        if (num > 0) {
            swarmRadio.disabled = false;
            swarmLabel.style.opacity = '1';
            swarmLabel.style.pointerEvents = 'auto';
            swarmLabel.style.cursor = 'pointer';
            swarmBadge.textContent = `${num} swarms`;
            swarmBadge.style.background = 'rgba(5,150,105,0.25)';
            swarmBadge.style.color = '#a7f3d0';
            swarmBadge.style.borderColor = 'rgba(16,185,129,0.4)';
            swarmLabel.title = `${num} seismic swarms detected in dataset`;
        } else {
            swarmRadio.disabled = true;
            if (swarmRadio.checked) {
                const accRadio = document.querySelector('input[name="anim_mode"][value="accumulation"]');
                if (accRadio) {
                    accRadio.checked = true;
                    toggleWindowInput();
                }
            }
            swarmLabel.style.opacity = '0.45';
            swarmLabel.style.pointerEvents = 'none';
            swarmLabel.style.cursor = 'not-allowed';
            swarmBadge.textContent = 'None detected';
            swarmBadge.style.background = 'rgba(239,68,68,0.15)';
            swarmBadge.style.color = '#fca5a5';
            swarmBadge.style.borderColor = 'rgba(239,68,68,0.3)';
            swarmLabel.title = 'No seismic swarms found in this dataset';
        }
    }

    // Instant Restoration from localStorage
    (function() {
        const cachedBadge = localStorage.getItem('hub_badge');
        const cachedDays = localStorage.getItem('hub_total_days');
        const cachedSwarms = localStorage.getItem('hub_swarms_count');
        const cachedEvents = localStorage.getItem('hub_event_count');
        if (cachedDays) window.currentDatasetTotalDays = parseInt(cachedDays, 10);
        if (cachedSwarms) window.currentDatasetSwarmsCount = parseInt(cachedSwarms, 10);
        if (cachedEvents) window.currentDatasetEventCount = parseInt(cachedEvents, 10);
        if (cachedBadge) {
            showHub(cachedBadge, window.currentDatasetTotalDays, window.currentDatasetSwarmsCount, window.currentDatasetEventCount);
        } else {
            document.getElementById('view-picker').classList.add('active');
        }
    })();

    // Verification via API
    window.addEventListener('pywebviewready', async function() {
        try {
            const info = await pywebview.api.get_csv_info();
            if (info && info.filename) {
                showHub(info.filename, info.total_days, info.swarms_count, info.event_count);
            } else {
                localStorage.removeItem('hub_badge');
                showFilePicker();
                refreshRecentFiles();
            }
        } catch(e) {
            showFilePicker();
            refreshRecentFiles();
        }
    });

    async function refreshRecentFiles() {
        const section = document.getElementById('recent-files-section');
        const list = document.getElementById('recent-list');
        try {
            const history = await pywebview.api.get_history();
            if (history && history.length > 0) {
                list.innerHTML = '';
                history.forEach(item => {
                    const btn = document.createElement('button');
                    btn.className = 'recent-item';
                    btn.innerHTML = `
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                        <span>${item.name}</span>
                    `;
                    btn.onclick = () => loadRecent(item.path);
                    list.appendChild(btn);
                });
                section.style.display = 'block';
            } else {
                section.style.display = 'none';
            }
        } catch(e) {
            section.style.display = 'none';
        }
    }

    async function clearRecentHistoryJS() {
        try {
            const res = await pywebview.api.clear_recent_history();
            if (res && res.status === 'success') {
                refreshRecentFiles();
            } else {
                showToast(res?.error || 'Failed to clear history', 'error');
            }
        } catch(e) {
            showToast('System error: ' + e, 'error');
        }
    }

    async function loadRecent(path) {
        const btn = document.getElementById('pick-btn');
        const loader = document.getElementById('loader');
        const progressBar = document.getElementById('progress-bar');
        progressBar.style.width = '0%';
        
        btn.disabled = true;
        loader.style.display = 'block';
        document.getElementById('recent-files-section').style.display = 'none';
        updateProgress('Accessing recent file...');

        try {
            const result = await pywebview.api.load_recent_file(path);
            if (result && !result.error) {
                // Success
                document.getElementById('fi-name').textContent = result.filename;
                document.getElementById('fi-count').textContent = result.event_count.toLocaleString() + ' quakes recovered';
                document.getElementById('fi-range').textContent = result.date_range;
                
                progressBar.style.width = '100%';
                setTimeout(() => {
                    showHub(result.filename, result.total_days, result.swarms_count, result.event_count);
                }, 400);
            } else {
                showToast(result?.error || 'Failed to load recent file', 'error');
                btn.disabled = false;
                loader.style.display = 'none';
                refreshRecentFiles();
            }
        } catch(e) {
            showToast('System error: ' + e, 'error');
            btn.disabled = false;
            loader.style.display = 'none';
        }
    }

    // --- File Picker Functions ---
    async function selectFile() {
        const btn = document.getElementById('pick-btn');
        const status = document.getElementById('status');
        const card = document.getElementById('file-card');
        const loader = document.getElementById('loader');
        const progressBar = document.getElementById('progress-bar');
        progressBar.style.width = '0%';

        btn.disabled = true;
        status.innerHTML = '';
        card.style.display = 'none';
        try {
            const result = await pywebview.api.select_csv();
            if (!result) {
                btn.disabled = false;
                document.getElementById('recent-files-section').style.display = 'block'; // Ensure it's still there
                return;
            }
            document.getElementById('recent-files-section').style.display = 'none';
            if (result.error) {
                status.className = 'status-msg status-error';
                status.textContent = result.error;
                btn.disabled = false;
                document.getElementById('recent-files-section').style.display = 'block';
                return;
            }

            // Success
            document.getElementById('fi-name').textContent = result.filename;
            document.getElementById('fi-count').textContent = result.event_count.toLocaleString() + ' quakes recovered';
            document.getElementById('fi-range').textContent = result.date_range;
            
            card.style.display = 'block';
            status.className = 'status-msg status-ok';
            status.textContent = 'Dataset validated successfully';
            loader.style.display = 'block';

            // Fake progress for aesthetic
            let p = 0;
            const interval = setInterval(() => {
                p += Math.random() * 20;
                if (p > 100) p = 100;
                progressBar.style.width = p + '%';
                if (p === 100) {
                    clearInterval(interval);
                    // Fade into Hub instead of full navigate
                    showHub(result.filename, result.total_days, result.swarms_count, result.event_count);
                }
            }, 100);

        } catch(e) {
            status.className = 'status-msg status-error';
            status.textContent = 'System error: ' + e;
            btn.disabled = false;
        }
    }

    function changeFileJS() {
        // Clear via API, then show picker
        pywebview.api.change_file().then(() => {
            localStorage.removeItem('hub_badge');
            localStorage.removeItem('hub_total_days');
            localStorage.removeItem('hub_swarms_count');
            localStorage.removeItem('hub_event_count');
            showFilePicker();
            refreshRecentFiles();
        }).catch(() => {
            showFilePicker();
            refreshRecentFiles();
        });
    }

    async function saveCurrentCsvJS() {
        const btn = document.getElementById('export-csv-btn');
        if (btn) btn.disabled = true;
        try {
            const res = await pywebview.api.save_current_csv();
            if (res && res.status === 'success') {
                const filename = res.path ? res.path.split(/[/\\]/).pop() : 'dataset.csv';
                showToast(`Dataset saved: ${filename}`, 'success');
            } else if (res && res.status === 'cancelled') {
                // User dismissed the system dialog - do nothing
            } else if (res && res.error) {
                showToast(res.error, 'error');
            }
        } catch(e) {
            showToast('Save failed: ' + e, 'error');
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    async function clearCacheJS() {
        const overlay = document.getElementById('overlay');
        document.getElementById('overlay-msg').textContent = 'Clearing Cache...';
        overlay.classList.add('show');
        
        try {
            const res = await pywebview.api.clear_map_cache();
            overlay.classList.remove('show');
            if (res === true) {
                refreshRecentFiles();
            } else {
                showToast('Error clearing cache: ' + res, 'error');
            }
        } catch(e) {
            overlay.classList.remove('show');
            showToast('System error: ' + e, 'error');
        }
    }

    function showToast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icon = type === 'success' ? 
            '<svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>' :
            '<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';
            
        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-message">${message}</div>
        `;
        
        container.appendChild(toast);
        
        // Trigger reflow for animation
        setTimeout(() => toast.classList.add('show'), 10);
        
        // Remove after delay
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 400);
        }, 2000);

    }


    // --- Hub Functions ---
    let loading = false;

    function openAnimModal() { 
        updateSwarmOptionState(window.currentDatasetSwarmsCount);
        toggleWindowInput();
        document.getElementById('anim-modal').classList.add('show'); 
    }
    function closeAnimModal() { document.getElementById('anim-modal').classList.remove('show'); }
    
    function openOnlineImportModal() { 
        // Set default dates if empty
        const startInput = document.getElementById('online-date-start');
        const endInput = document.getElementById('online-date-end');
        if (!startInput.value || !endInput.value) {
            const now = new Date();
            const lastYear = new Date();
            lastYear.setFullYear(now.getFullYear() - 1);
            
            endInput.value = now.toISOString().split('T')[0];
            startInput.value = lastYear.toISOString().split('T')[0];
        }
        document.getElementById('online-import-modal').classList.add('show'); 
    }
    function closeOnlineImportModal() { document.getElementById('online-import-modal').classList.remove('show'); }
    
    async function submitOnlineImport() {
        const params = {
            network: document.getElementById('online-area').value,
            format: document.getElementById('online-format')?.value || 'csv',
            minmag: document.getElementById('online-mag-min').value || 0.0,
            maxmag: document.getElementById('online-mag-max').value || 10.0,
            startdate: document.getElementById('online-date-start').value,
            starttime: document.getElementById('online-time-start').value,
            enddate: document.getElementById('online-date-end').value,
            endtime: document.getElementById('online-time-end').value,
            level: document.getElementById('online-livello').value,
            located: document.getElementById('online-solo-localizzati').checked,
            excludeMissing: document.getElementById('online-exclude-missing').checked
        };

        if (!params.network) {
            showToast('Please select a geographic area.', 'error');
            return;
        }
        if (!params.startdate || !params.enddate) {
            showToast('Please enter valid start and end dates.', 'error');
            return;
        }

        closeOnlineImportModal();
        
        const btn = document.getElementById('online-pick-btn');
        const loader = document.getElementById('loader');
        const progressBar = document.getElementById('progress-bar');
        
        btn.disabled = true;
        loader.style.display = 'block';
        document.getElementById('recent-files-section').style.display = 'none';
        progressBar.style.width = '10%';
        updateProgress('Connecting to INGV...');

        try {
            const result = await pywebview.api.download_online_data(params);
            if (result && !result.error) {
                document.getElementById('fi-name').textContent = result.filename;
                document.getElementById('fi-count').textContent = result.event_count.toLocaleString() + ' quakes imported';
                document.getElementById('fi-range').textContent = result.date_range;
                
                progressBar.style.width = '100%';
                setTimeout(() => {
                    showHub(result.filename, result.total_days, result.swarms_count, result.event_count);
                    btn.disabled = false;
                }, 400);
            } else {
                showToast(result?.error || 'Import failed', 'error');
                btn.disabled = false;
                loader.style.display = 'none';
                refreshRecentFiles();
            }
        } catch(e) {
            showToast('System error: ' + e, 'error');
            btn.disabled = false;
            loader.style.display = 'none';
            refreshRecentFiles();
        }
    }

    function toggleWindowInput() {
        const checkedRadio = document.querySelector('input[name="anim_mode"]:checked');
        if (!checkedRadio) return;
        const mode = checkedRadio.value;
        const winGroup = document.getElementById('window_input_group');
        const stepGroup = document.getElementById('step_input_group');
        const label = document.getElementById('duration_label');
        if (mode === 'accumulation' || mode === 'swarm') {
            winGroup.style.display = 'none';
            stepGroup.style.display = 'none';
        } else if (mode === 'window') {
            winGroup.style.display = 'block';
            winGroup.style.opacity = '1';
            winGroup.style.pointerEvents = 'auto';
            label.textContent = "Time Window (days):";
            stepGroup.style.display = 'none';
        } else if (mode === 'block') {
            winGroup.style.display = 'block';
            winGroup.style.opacity = '1';
            winGroup.style.pointerEvents = 'auto';
            label.textContent = "Time Window (days):";
            stepGroup.style.display = 'block';
            stepGroup.style.opacity = '1';
            stepGroup.style.pointerEvents = 'auto';
        }
    }
    async function launchAnimation() {
        const mode = document.querySelector('input[name="anim_mode"]:checked').value;
        const days = parseInt(document.getElementById('window_days').value);
        const step = parseInt(document.getElementById('step_days').value);
        
        if (mode === 'window') {
            if (isNaN(days) || days < 1) {
                showToast('Error: Please enter a valid number of days (≥ 1).', 'error');
                return;
            }
            if (window.currentDatasetTotalDays && days > window.currentDatasetTotalDays) {
                showToast(`Error: Time window (${days} days) exceeds dataset duration (${window.currentDatasetTotalDays} days).`, 'error');
                return;
            }
        } else if (mode === 'block') {
            if (isNaN(days) || days < 1 || isNaN(step) || step < 1) {
                showToast('Error: Time window and step must be positive integers greater than 0.', 'error');
                return;
            }
            if (window.currentDatasetTotalDays) {
                if (days > window.currentDatasetTotalDays || step > window.currentDatasetTotalDays) {
                    showToast(`Error: Specified values exceed dataset duration (${window.currentDatasetTotalDays} days).`, 'error');
                    return;
                }
            }
        }
        
        closeAnimModal();
        await loadView(2, mode, days || 30, step || 7);
    }

    const VIEW_LABELS = { 
        0: 'Rendering Visualization...', 
        1: 'Rendering Visualization...', 
        2: 'Rendering Animation...', 
        3: 'Rendering Cluster Analysis...' 
    };

    async function loadView(style, anim_mode='accumulation', window_days=30, step_days=7, clustering_method='dbscan') {
        if (loading) return;
        loading = true;

        const overlay = document.getElementById('overlay');
        if (style === 2 && anim_mode === 'swarm') {
            document.getElementById('overlay-msg').textContent = 'Rendering INGV Swarm Animation...';
        } else {
            document.getElementById('overlay-msg').textContent = VIEW_LABELS[style] || 'Loading...';
        }
        overlay.classList.add('show');

        try {
            await pywebview.api.load_view(style, anim_mode, window_days, step_days, clustering_method);
            // Hide overlay is not needed here as python will trigger a window load
            // but in case it fails midway:
            setTimeout(() => { loading = false; }, 3000); 
        } catch(e) {
            overlay.classList.remove('show');
            loading = false;
            showToast('Engine failure: ' + e, 'error');
        }

    }

    function toggleHubShortcuts(e, forceState = null) {
        if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
        const modal = document.getElementById('hub-shortcuts-modal');
        if (!modal) return;
        if (forceState === false) {
            modal.classList.remove('active');
        } else if (forceState === true) {
            modal.classList.add('active');
        } else {
            modal.classList.toggle('active');
        }
    }

    document.addEventListener('click', (e) => {
        const card = e.target.closest('.vcard');
        if (card) {
            card.classList.add('card-pulse');
            setTimeout(() => card.classList.remove('card-pulse'), 550);
        }

        const modal = document.getElementById('hub-shortcuts-modal');
        if (modal && modal.classList.contains('active')) {
            if (!e.target.closest('#hub-shortcuts-modal') && !e.target.closest('#hub-shortcuts-btn')) {
                toggleHubShortcuts(null, false);
            }
        }
    });

    // Global keyboard shortcuts in Hub
    window.addEventListener('keydown', (e) => {
        // Prevent accidental page reload in desktop application
        if (e.key === 'F5' || ((e.ctrlKey || e.metaKey) && (e.key === 'r' || e.key === 'R'))) {
            e.preventDefault();
            return;
        }

        const target = e.target;
        const tag = (target && target.tagName) ? target.tagName.toLowerCase() : '';
        if (tag === 'input' || tag === 'textarea' || tag === 'select' || (target && target.isContentEditable)) {
            // Allow Enter key inside the animation window inputs to launch animation
            if (e.key === 'Enter') {
                const modal = document.getElementById('anim-modal');
                if (modal && modal.style.display === 'block') {
                    e.preventDefault();
                    launchAnimation();
                }
            }
            return;
        }

        // Escape: Close animation modal or shortcuts modal if open
        if (e.key === 'Escape') {
            const scModal = document.getElementById('hub-shortcuts-modal');
            if (scModal && scModal.classList.contains('active')) {
                e.preventDefault();
                toggleHubShortcuts(null, false);
                return;
            }
            const modal = document.getElementById('anim-modal');
            if (modal && modal.style.display === 'block') {
                e.preventDefault();
                closeAnimModal();
                return;
            }
        }

        // H / ? / F1: Toggle Keyboard Shortcuts Modal
        if (e.key === 'h' || e.key === 'H' || e.code === 'KeyH' || e.key === '?' || e.key === 'F1') {
            if (!e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                toggleHubShortcuts();
                return;
            }
        }

        // Keys 1 - 4: Fast direct navigation into the views from Hub
        if (['1', '2', '3', '4'].includes(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey) {
            const hub = document.getElementById('view-hub');
            if (!hub || !hub.classList.contains('active')) {
                return;
            }
            e.preventDefault();
            const modal = document.getElementById('anim-modal');
            if (modal && modal.style.display === 'block') {
                closeAnimModal();
            }
            toggleHubShortcuts(null, false);

            const viewIndexMap = {
                '1': 0, // 2D Map
                '2': 1, // 3D Static
                '3': 2, // 3D Animated
                '4': 3  // 3D Clustering
            };
            loadView(viewIndexMap[e.key]);
        }
    });

    function purgeFrameContext(frame) {
        if (!frame || !frame.contentWindow) return;
        try {
            const win = frame.contentWindow;
            // 1. Destroy socket connection & cancel reconnect timers
            if (win.seismicSocket && typeof win.seismicSocket.destroy === 'function') {
                win.seismicSocket.destroy();
            }
            // 2. Purge Plotly graph instances
            if (win.Plotly) {
                const plots = win.document.querySelectorAll('.js-plotly-plot, .plotly-graph-div');
                plots.forEach(p => {
                    try { win.Plotly.purge(p); } catch(e) {}
                });
            }
            // 3. Forcibly release WebGL hardware contexts via WEBGL_lose_context
            const canvases = win.document.querySelectorAll('canvas');
            canvases.forEach(c => {
                try {
                    const gl = c.getContext('webgl') || c.getContext('webgl2') || c.getContext('experimental-webgl');
                    if (gl) {
                        const loseExt = gl.getExtension('WEBGL_lose_context');
                        if (loseExt) loseExt.loseContext();
                    }
                } catch(e) {}
            });
            // 4. Clear any registered requestAnimationFrames or body nodes
            try {
                if (win.animInterval) win.clearInterval(win.animInterval);
                if (win.cinemaInterval) win.clearInterval(win.cinemaInterval);
                if (win.document && win.document.body) {
                    win.document.body.innerHTML = '';
                }
            } catch(e) {}
        } catch(e) {}
    }

    /* ─── SPA Window Controller ─── */
    window.SeismicApp = {
        _revealTimeout: null,
        showOverlay: function(msg) {
            const overlay = document.getElementById('overlay');
            const overlayMsg = document.getElementById('overlay-msg');
            if (overlayMsg && msg) overlayMsg.textContent = msg;
            if (overlay) overlay.classList.add('show');
            loading = true;
        },
        navigateTo: function(url) {
            const frame = document.getElementById('viz-frame');
            const overlay = document.getElementById('overlay');
            if (this._revealTimeout) clearTimeout(this._revealTimeout);

            // Cleanly purge any active WebGL / Plotly / Socket context from previous view
            if (frame && frame.src && frame.src !== 'about:blank') {
                purgeFrameContext(frame);
            }

            // Keep overlay visible and dark during transition
            if (overlay) overlay.classList.add('show');
            
            // Frame is prepared in background at opacity 0
            frame.style.display = 'block';
            frame.style.opacity = '0';
            frame.src = url;

            // Safe fallback: in case the view does not signal ready after 8s
            this._revealTimeout = setTimeout(() => {
                this.revealVisualization();
            }, 8000);
        },
        revealVisualization: function() {
            if (this._revealTimeout) {
                clearTimeout(this._revealTimeout);
                this._revealTimeout = null;
            }
            const frame = document.getElementById('viz-frame');
            const overlay = document.getElementById('overlay');
            if (frame) {
                frame.style.opacity = '1';
            }
            // Smooth dissolvenza: wait for frame crossfade before releasing overlay
            setTimeout(() => {
                if (overlay) overlay.classList.remove('show');
                loading = false;
            }, 200);
        },
        hideOverlay: function() {
            this.revealVisualization();
        },
        showHub: function() {
            if (this._revealTimeout) {
                clearTimeout(this._revealTimeout);
                this._revealTimeout = null;
            }
            const frame = document.getElementById('viz-frame');
            const overlay = document.getElementById('overlay');
            if (frame) {
                frame.style.opacity = '0';
                purgeFrameContext(frame);
            }
            setTimeout(() => {
                if (frame) {
                    frame.style.display = 'none';
                    frame.src = 'about:blank';
                }
                if (overlay) overlay.classList.remove('show');
                loading = false;
            }, 350);
            if (typeof updateRecentFiles === 'function') updateRecentFiles();
            if (typeof updateCardInfo === 'function') updateCardInfo();
        }
    };

    // --- Drag & Drop File Import ---
    function initDragAndDrop() {
        const picker = document.getElementById('view-picker');
        const container = document.querySelector('.container');
        if (!picker || !container) return;

        let dragCounter = 0;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            window.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        window.addEventListener('dragenter', (e) => {
            if (!picker.classList.contains('active')) return;
            dragCounter++;
            container.classList.add('drag-active');
        });

        window.addEventListener('dragleave', (e) => {
            if (!picker.classList.contains('active')) return;
            dragCounter--;
            if (dragCounter <= 0) {
                dragCounter = 0;
                container.classList.remove('drag-active');
            }
        });

        window.addEventListener('drop', async (e) => {
            dragCounter = 0;
            container.classList.remove('drag-active');
            if (!picker.classList.contains('active')) return;

            const dt = e.dataTransfer;
            const files = dt?.files;
            if (!files || files.length === 0) return;

            const file = files[0];
            const lowerName = file.name.toLowerCase();
            if (!lowerName.endsWith('.csv') && !lowerName.endsWith('.geojson') && !lowerName.endsWith('.json')) {
                showToast('Please drop a valid dataset file (.csv, .geojson, .json)', 'error');
                return;
            }

            handleDroppedFile(file);
        });
    }

    async function handleDroppedFile(file) {
        const btn = document.getElementById('pick-btn');
        const status = document.getElementById('status');
        const card = document.getElementById('file-card');
        const loader = document.getElementById('loader');
        const progressBar = document.getElementById('progress-bar');

        btn.disabled = true;
        status.innerHTML = '';
        card.style.display = 'none';
        loader.style.display = 'block';
        progressBar.style.width = '25%';
        document.getElementById('recent-files-section').style.display = 'none';

        try {
            let result = null;
            // 1. Try native file path if supported by WebKit / pywebview
            if (file.path && window.pywebview?.api?.load_recent_file) {
                updateProgress('Reading local file...');
                result = await pywebview.api.load_recent_file(file.path);
            }

            // 2. Fallback via file text content (100% reliable)
            if (!result || result.error) {
                updateProgress('Importing dataset content...');
                const text = await file.text();
                result = await pywebview.api.load_csv_content(file.name, text);
            }

            if (!result || result.error) {
                status.className = 'status-msg status-error';
                status.textContent = result?.error || 'Failed to process dropped dataset file.';
                btn.disabled = false;
                loader.style.display = 'none';
                document.getElementById('recent-files-section').style.display = 'block';
                return;
            }

            // Success
            document.getElementById('fi-name').textContent = result.filename;
            document.getElementById('fi-count').textContent = result.event_count.toLocaleString() + ' quakes recovered';
            document.getElementById('fi-range').textContent = result.date_range;

            card.style.display = 'block';
            status.className = 'status-msg status-ok';
            status.textContent = 'Dataset loaded via Drag & Drop';
            progressBar.style.width = '100%';

            setTimeout(() => {
                showHub(result.filename, result.total_days, result.swarms_count, result.event_count);
            }, 400);

        } catch(err) {
            status.className = 'status-msg status-error';
            status.textContent = 'Error loading dropped file: ' + err;
            btn.disabled = false;
            loader.style.display = 'none';
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initDragAndDrop);
    } else {
        initDragAndDrop();
    }
