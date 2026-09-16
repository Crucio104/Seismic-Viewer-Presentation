// --- Seismic Viewer: Modular Camera Subsystem (Presets, Orbit, Persistence & WebGL Smoothing) ---
(function() {
    'use strict';

    const CAMERA_STORAGE_KEY = 'seismic_custom_camera_orientation';

    const SIDE_VIEWS = [
        { eye: { x: 0, y: -1.8, z: 0.15 }, up: { x: 0, y: 0, z: 1 }, center: { x: 0, y: 0, z: 0 } },  // 0: South / Front
        { eye: { x: 1.8, y: 0, z: 0.15 }, up: { x: 0, y: 0, z: 1 }, center: { x: 0, y: 0, z: 0 } },   // 1: East / Right
        { eye: { x: 0, y: 1.8, z: 0.15 }, up: { x: 0, y: 0, z: 1 }, center: { x: 0, y: 0, z: 0 } },   // 2: North / Back
        { eye: { x: -1.8, y: 0, z: 0.15 }, up: { x: 0, y: 0, z: 1 }, center: { x: 0, y: 0, z: 0 } }   // 3: West / Left
    ];

    let currentSideIndex = -1;
    let isProgrammaticCameraChange = false;
    let lastProgrammaticChangeTime = 0;
    let smoothCameraReqId = null;
    let activeCameraEye = null;
    let activeCameraUp = null;
    let activeCameraCenter = null;
    let isRelayoutBusy = false;
    let pendingRelayoutData = null;

    let cinemaModeActive = false;
    let cinemaAngle = 0;
    let cinemaReqId = null;

    function getPlotlyElement() {
        if (window.plotlyId) {
            const el = document.getElementById(window.plotlyId);
            if (el) return el;
        }
        const gd = document.querySelector('.plotly-graph-div') || document.getElementById('plot') || document.getElementById('plotly-div');
        if (gd && gd.id) window.plotlyId = gd.id;
        return gd;
    }

    function getPlotlyGlScene(gd) {
        if (!gd || !gd._fullLayout) return null;
        const subplots = gd._fullLayout._subplots;
        const gl3dList = (subplots && subplots.gl3d) ? subplots.gl3d : ['scene'];
        for (const sName of gl3dList) {
            const scene = gd._fullLayout[sName] ? gd._fullLayout[sName]._scene : null;
            if (scene && scene.camera && scene.glplot) return scene;
        }
        return null;
    }

    function renderDirectCameraFrame(gd, eye, up, center) {
        const scene = getPlotlyGlScene(gd);
        if (scene && typeof scene.setViewport === 'function' && scene.glplot && typeof scene.glplot.redraw === 'function') {
            try {
                scene.setViewport({
                    camera: {
                        eye: eye,
                        center: center,
                        up: up,
                        projection: { type: 'perspective' }
                    },
                    aspectratio: (scene.fullSceneLayout && scene.fullSceneLayout.aspectratio) ? scene.fullSceneLayout.aspectratio : { x: 1, y: 1, z: 1 }
                });
                scene.glplot.redraw();
                return true;
            } catch (err) {
                return false;
            }
        }
        return false;
    }

    function dispatchCameraRelayout(gd, eye, up, center, dragmode) {
        const update = {
            'scene.camera.eye': eye,
            'scene.camera.up': up,
            'scene.camera.center': center
        };
        if (dragmode) update['scene.dragmode'] = dragmode;

        if (isRelayoutBusy) {
            pendingRelayoutData = update;
            return;
        }

        isRelayoutBusy = true;
        pendingRelayoutData = null;
        Plotly.relayout(gd, update).then(() => {
            isRelayoutBusy = false;
            if (pendingRelayoutData) {
                const next = pendingRelayoutData;
                pendingRelayoutData = null;
                dispatchCameraRelayout(gd, next['scene.camera.eye'], next['scene.camera.up'], next['scene.camera.center'], next['scene.dragmode']);
            }
        }).catch(() => {
            isRelayoutBusy = false;
        });
    }

    function setupCameraRelayoutWatcher(gd) {
        if (!gd || gd._cameraRelayoutWatcherHooked) return;
        gd._cameraRelayoutWatcherHooked = true;

        if (typeof gd.on === 'function') {
            gd.on('plotly_relayout', function(eventData) {
                if (isProgrammaticCameraChange || cinemaModeActive || (performance.now() - lastProgrammaticChangeTime < 350)) return;
                if (eventData && (
                    eventData['scene.camera'] !== undefined ||
                    eventData['scene.camera.eye'] !== undefined ||
                    eventData['scene.camera.center'] !== undefined ||
                    eventData['scene.camera.up'] !== undefined ||
                    Object.keys(eventData).some(k => k.startsWith('scene.camera'))
                )) {
                    currentSideIndex = -1;
                    activeCameraEye = null;
                    activeCameraUp = null;
                    activeCameraCenter = null;
                }
            });
        }

        gd.addEventListener('pointerdown', function(e) {
            if (e.target && e.target.closest && e.target.closest('#camera-controls, .glass-panel, button, input')) return;
            const startX = e.clientX;
            const startY = e.clientY;

            function onPointerMove(moveEvent) {
                if (Math.hypot(moveEvent.clientX - startX, moveEvent.clientY - startY) > 5) {
                    currentSideIndex = -1;
                    activeCameraEye = null;
                    activeCameraUp = null;
                    activeCameraCenter = null;
                }
            }

            function onPointerUp() {
                window.removeEventListener('pointermove', onPointerMove);
                window.removeEventListener('pointerup', onPointerUp);
            }

            window.addEventListener('pointermove', onPointerMove);
            window.addEventListener('pointerup', onPointerUp);
        });

        gd.addEventListener('wheel', function() {
            currentSideIndex = -1;
            activeCameraEye = null;
            activeCameraUp = null;
            activeCameraCenter = null;
        }, { passive: true });
    }

    function updatePasteButtonState() {
        const pasteBtn = document.getElementById('btn-cam-paste');
        if (!pasteBtn) return;
        let hasSaved = false;
        try {
            const item = localStorage.getItem(CAMERA_STORAGE_KEY);
            if (item) {
                const parsed = JSON.parse(item);
                if (parsed && parsed.eye) hasSaved = true;
            }
        } catch (e) {
            hasSaved = false;
        }

        if (hasSaved) {
            pasteBtn.disabled = false;
            pasteBtn.classList.remove('disabled');
            pasteBtn.title = 'Paste Saved Camera Orientation';
        } else {
            pasteBtn.disabled = true;
            pasteBtn.classList.add('disabled');
            pasteBtn.title = 'Paste Saved Camera Orientation (No orientation saved)';
        }
    }

    window.addEventListener('storage', function(e) {
        if (e.key === CAMERA_STORAGE_KEY) {
            updatePasteButtonState();
        }
    });

    function smoothAnimateCamera(targetEye, targetUp, targetCenter) {
        const gd = getPlotlyElement();
        if (!gd || !gd.layout || !gd.layout.scene) return Promise.resolve();

        if (smoothCameraReqId) {
            cancelAnimationFrame(smoothCameraReqId);
            smoothCameraReqId = null;
        }

        let cam = gd.layout.scene.camera || {};
        let startEye = activeCameraEye ? { ...activeCameraEye } : (cam.eye ? { ...cam.eye } : { x: 1.25, y: 1.25, z: 1.25 });
        let startUp  = activeCameraUp  ? { ...activeCameraUp }  : (cam.up  ? { ...cam.up }  : { x: 0, y: 0, z: 1 });
        let startCenter = activeCameraCenter ? { ...activeCameraCenter } : (cam.center ? { ...cam.center } : { x: 0, y: 0, z: 0 });

        const rXY1 = Math.hypot(startEye.x, startEye.y);
        const rXY2 = Math.hypot(targetEye.x, targetEye.y);
        let theta1 = Math.atan2(startEye.y, startEye.x);
        let theta2 = Math.atan2(targetEye.y, targetEye.x);
        let dTheta = 0;

        if (rXY1 >= 0.001 && rXY2 >= 0.001) {
            dTheta = theta2 - theta1;
            while (dTheta > Math.PI) dTheta -= 2 * Math.PI;
            while (dTheta < -Math.PI) dTheta += 2 * Math.PI;
        } else if (rXY1 < 0.001) {
            theta1 = theta2;
            dTheta = 0;
        } else {
            theta2 = theta1;
            dTheta = 0;
        }

        const duration = 450;
        const startTime = performance.now();
        isProgrammaticCameraChange = true;
        lastProgrammaticChangeTime = startTime;

        return new Promise((resolve) => {
            function step(now) {
                const elapsed = now - startTime;
                const t = Math.min(elapsed / duration, 1);
                const ease = (1 - Math.cos(t * Math.PI)) / 2;

                let currentEye;
                if (rXY1 >= 0.001 || rXY2 >= 0.001) {
                    const currentR = rXY1 + (rXY2 - rXY1) * ease;
                    const currentTheta = theta1 + dTheta * ease;
                    currentEye = {
                        x: currentR * Math.cos(currentTheta),
                        y: currentR * Math.sin(currentTheta),
                        z: startEye.z + (targetEye.z - startEye.z) * ease
                    };
                } else {
                    currentEye = {
                        x: startEye.x + (targetEye.x - startEye.x) * ease,
                        y: startEye.y + (targetEye.y - startEye.y) * ease,
                        z: startEye.z + (targetEye.z - startEye.z) * ease
                    };
                }

                const currentUp = {
                    x: startUp.x + (targetUp.x - startUp.x) * ease,
                    y: startUp.y + (targetUp.y - startUp.y) * ease,
                    z: startUp.z + (targetUp.z - startUp.z) * ease
                };
                const currentCenter = {
                    x: startCenter.x + (targetCenter.x - startCenter.x) * ease,
                    y: startCenter.y + (targetCenter.y - startCenter.y) * ease,
                    z: startCenter.z + (targetCenter.z - startCenter.z) * ease
                };

                activeCameraEye = currentEye;
                activeCameraUp = currentUp;
                activeCameraCenter = currentCenter;

                if (t >= 1) {
                    smoothCameraReqId = null;
                    activeCameraEye = { ...targetEye };
                    activeCameraUp = { ...targetUp };
                    activeCameraCenter = { ...targetCenter };

                    lastProgrammaticChangeTime = performance.now();
                    Plotly.relayout(gd, {
                        'scene.camera.eye': targetEye,
                        'scene.camera.up': targetUp,
                        'scene.camera.center': targetCenter
                    }).then(() => {
                        setTimeout(() => {
                            isProgrammaticCameraChange = false;
                        }, 120);
                        resolve();
                    }).catch(() => {
                        isProgrammaticCameraChange = false;
                        resolve();
                    });
                } else {
                    const renderedDirectly = renderDirectCameraFrame(gd, currentEye, currentUp, currentCenter);
                    if (!renderedDirectly) {
                        dispatchCameraRelayout(gd, currentEye, currentUp, currentCenter);
                    }
                    smoothCameraReqId = requestAnimationFrame(step);
                }
            }

            smoothCameraReqId = requestAnimationFrame(step);
        });
    }

    function snapToView(view) {
        if (cinemaModeActive && view !== 'reset' && view !== 'cinema_reset') toggleCinemaMode();
        const gd = getPlotlyElement();
        if (!gd || !gd.layout) return Promise.resolve();

        const mapLayout = gd.layout.mapbox || gd.layout.map;
        if (mapLayout) {
            currentSideIndex = -1;
            activeCameraEye = null;
            if (view === 'reset') {
                const initView = window._initial2DMapboxView;
                if (initView) {
                    const update = gd.layout.mapbox ? {
                        'mapbox.center': initView.center,
                        'mapbox.zoom': initView.zoom,
                        'mapbox.pitch': 0,
                        'mapbox.bearing': 0
                    } : {
                        'map.center': initView.center,
                        'map.zoom': initView.zoom,
                        'map.pitch': 0,
                        'map.bearing': 0
                    };
                    return Plotly.relayout(gd, update);
                }
            } else if (view === 'top') {
                const update = gd.layout.mapbox ? {
                    'mapbox.pitch': 0,
                    'mapbox.bearing': 0
                } : {
                    'map.pitch': 0,
                    'map.bearing': 0
                };
                return Plotly.relayout(gd, update);
            }
            return Promise.resolve();
        }

        if (!gd.layout.scene) return Promise.resolve();

        let targetEye = { x: 1.25, y: 1.25, z: 1.25 };
        let targetUp = { x: 0, y: 0, z: 1 };
        let targetCenter = { x: 0, y: 0, z: 0 };

        if (view === 'top') {
            currentSideIndex = -1;
            targetEye = { x: 0, y: -0.01, z: 2.1 };
        } else if (view === 'side') {
            if (currentSideIndex < 0 || currentSideIndex >= SIDE_VIEWS.length) {
                currentSideIndex = 0;
            } else {
                currentSideIndex = (currentSideIndex + 1) % SIDE_VIEWS.length;
            }
            const sideCfg = SIDE_VIEWS[currentSideIndex];
            targetEye = sideCfg.eye;
            targetUp = sideCfg.up;
            targetCenter = sideCfg.center;
        } else if (view === 'cinema_reset') {
            currentSideIndex = -1;
            targetEye = { x: 1.27, y: 1.27, z: 1.0 };
        } else if (view === 'reset') {
            currentSideIndex = -1;
            targetEye = { x: 1.25, y: 1.25, z: 1.25 };
        }

        return smoothAnimateCamera(targetEye, targetUp, targetCenter);
    }

    function toggleCinemaMode() {
        currentSideIndex = -1;
        const gd = getPlotlyElement();
        if (!gd || !gd.layout || !gd.layout.scene) {
            if (typeof showStatusToast === 'function') showStatusToast('Preparing 3D scene...', true);
            return;
        }

        cinemaModeActive = !cinemaModeActive;
        const btn = document.getElementById('btn-cinema');

        if (cinemaModeActive) {
            if (btn) btn.classList.add('active');
            window._cinemaStartTime = null;
            snapToView('cinema_reset').then(() => {
                if (!cinemaModeActive) return;
                window._cinemaStartTime = performance.now();
                try {
                    const eye = gd.layout.scene.camera.eye || { x: 1.27, y: 1.27, z: 1.0 };
                    cinemaAngle = Math.atan2(eye.y, eye.x);
                } catch (e) {
                    cinemaAngle = Math.PI / 4;
                }
                animateCinema();
            });
        } else {
            if (btn) btn.classList.remove('active');
            window._cinemaStartTime = null;
            if (cinemaReqId) cancelAnimationFrame(cinemaReqId);
        }
    }

    function animateCinema() {
        if (!cinemaModeActive) return;
        const gd = getPlotlyElement();
        if (!gd || !gd.layout || !gd.layout.scene) return;

        if (!window._cinemaStartTime) window._cinemaStartTime = performance.now();
        const elapsed = performance.now() - window._cinemaStartTime;
        const ramp = Math.min(elapsed / 1500, 1);
        cinemaAngle += 0.005 * ramp;
        const radius = 1.8;

        try {
            const bgX = 50 + 10 * Math.cos(cinemaAngle);
            const bgY = 50 + 10 * Math.sin(cinemaAngle);
            document.body.style.setProperty('--bg-x', `${bgX}%`);
            document.body.style.setProperty('--bg-y', `${bgY}%`);

            const camEye = {
                x: radius * Math.cos(cinemaAngle),
                y: radius * Math.sin(cinemaAngle),
                z: 1.0
            };
            const renderedDirect = renderDirectCameraFrame(gd, camEye, { x: 0, y: 0, z: 1 }, { x: 0, y: 0, z: 0 });
            if (!renderedDirect) {
                Plotly.relayout(gd, { 'scene.camera.eye': camEye });
            }
        } catch (e) {
            console.warn("Auto-rotation frame skipped:", e);
        }

        cinemaReqId = requestAnimationFrame(animateCinema);
    }

    function copyCameraOrientation() {
        const gd = getPlotlyElement();
        if (!gd || !gd.layout || !gd.layout.scene) return;

        const cam = gd.layout.scene.camera;
        if (!cam) return;

        const eyeToSave = activeCameraEye ? { ...activeCameraEye } : (cam.eye ? { x: cam.eye.x, y: cam.eye.y, z: cam.eye.z } : { x: 1.25, y: 1.25, z: 1.25 });
        const upToSave = activeCameraUp ? { ...activeCameraUp } : (cam.up ? { x: cam.up.x, y: cam.up.y, z: cam.up.z } : { x: 0, y: 0, z: 1 });
        const centerToSave = activeCameraCenter ? { ...activeCameraCenter } : (cam.center ? { x: cam.center.x, y: cam.center.y, z: cam.center.z } : { x: 0, y: 0, z: 0 });

        const savedOrientation = {
            eye: eyeToSave,
            up: upToSave,
            center: centerToSave
        };

        try {
            localStorage.setItem(CAMERA_STORAGE_KEY, JSON.stringify(savedOrientation));
            updatePasteButtonState();
        } catch (e) {
            console.warn('Could not save camera orientation to localStorage:', e);
        }
    }

    function pasteCameraOrientation() {
        let savedOrientation = null;
        try {
            const str = localStorage.getItem(CAMERA_STORAGE_KEY);
            if (str) savedOrientation = JSON.parse(str);
        } catch (e) {
            console.error('Failed to read saved camera orientation:', e);
        }
        if (!savedOrientation || !savedOrientation.eye) return Promise.resolve();

        if (cinemaModeActive) toggleCinemaMode();
        currentSideIndex = -1;

        return smoothAnimateCamera(
            savedOrientation.eye,
            savedOrientation.up || { x: 0, y: 0, z: 1 },
            savedOrientation.center || { x: 0, y: 0, z: 0 }
        );
    }

    window.SeismicCamera = {
        snapToView,
        toggleCinemaMode,
        copyCameraOrientation,
        pasteCameraOrientation,
        updatePasteButtonState,
        setupCameraRelayoutWatcher,
        renderDirectCameraFrame
    };

    // Keep top-level window aliases intact so no existing handlers break
    window.snapToView = snapToView;
    window.toggleCinemaMode = toggleCinemaMode;
    window.copyCameraOrientation = copyCameraOrientation;
    window.pasteCameraOrientation = pasteCameraOrientation;
    window.updatePasteButtonState = updatePasteButtonState;
    window.setupCameraRelayoutWatcher = setupCameraRelayoutWatcher;
})();
