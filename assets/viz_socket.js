// --- Message Synchronization & WebSocket Subsystem ---
(function() {
    'use strict';

    class SeismicSocket {
        constructor() {
            this.socket = null;
            this.requests = new Map();
            this.requestId = 0;
            this.handlers = new Map();
            this._retryTimeout = null;
            this._destroyed = false;
            this.init();
        }

        init() {
            if (this._destroyed) return;
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            try {
                this.socket = new WebSocket(`${protocol}//${host}/ws`);
            } catch (e) {
                console.error("Socket instantiation error:", e);
                return;
            }

            this.socket.onopen = () => {
                if (this._destroyed) {
                    try { this.socket.close(); } catch(e) {}
                    return;
                }
                console.info("SeismicSocket: Connected to backend.");
                const ind = document.getElementById('ws-status');
                if (ind) { ind.classList.add('connected'); ind.title = 'Server Connected'; }
            };

            this.socket.onmessage = (event) => {
                if (this._destroyed) return;
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (e) {
                    console.error("Socket Message Error:", e);
                }
            };

            this.socket.onclose = () => {
                if (this._destroyed) return;
                console.warn("WebSocket disconnected.");
                const ind = document.getElementById('ws-status');
                if (ind) { ind.classList.remove('connected'); ind.title = 'Server Disconnected'; }
                if (this._retryTimeout) clearTimeout(this._retryTimeout);
                this._retryTimeout = setTimeout(() => {
                    if (!this._destroyed) this.init();
                }, 2000);
            };

            this.socket.onerror = () => {
                if (this.socket) {
                    try { this.socket.close(); } catch(e) {}
                }
            };
        }

        destroy() {
            this._destroyed = true;
            if (this._retryTimeout) {
                clearTimeout(this._retryTimeout);
                this._retryTimeout = null;
            }
            if (this.socket) {
                this.socket.onopen = null;
                this.socket.onmessage = null;
                this.socket.onerror = null;
                this.socket.onclose = null;
                try {
                    this.socket.close();
                } catch (e) {}
                this.socket = null;
            }
            this.requests.clear();
            this.handlers.clear();
        }

        handleMessage(data) {
            if (data.type === 'progress') {
                updateProgress(data.msg);
                // Flash indicator on activity
                const ind = document.getElementById('ws-status');
                if (ind) { ind.classList.add('activity'); setTimeout(() => ind.classList.remove('activity'), 200); }
            } else if (data.type === 'rpc_response') {
                const resolve = this.requests.get(data.id);
                if (resolve) {
                    resolve(data.result);
                    this.requests.delete(data.id);
                }
            }
            // Custom handlers
            const handler = this.handlers.get(data.type);
            if (handler) handler(data);
        }

        /**
         * Send an RPC-like request and await the response.
         */
        sendRequest(type, params) {
            return new Promise((resolve, reject) => {
                if (this._destroyed) return reject(new Error("Socket destroyed"));
                if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
                    // Try to wait a bit if connecting
                    if (this.socket && this.socket.readyState === WebSocket.CONNECTING) {
                        setTimeout(() => this.sendRequest(type, params).then(resolve).catch(reject), 500);
                        return;
                    }
                    return reject(new Error("Socket not connected"));
                }
                const id = this.requestId++;
                this.requests.set(id, resolve);
                this.socket.send(JSON.stringify({ type, id, params }));
            });
        }
        
        on(type, handler) {
            this.handlers.set(type, handler);
        }
    }

    function updateProgress(msg) {
        // Update the injected init-loader from Python templates
        const initLoaderText = document.querySelector('#init-loader .loader-text');
        if (initLoaderText) {
            initLoaderText.textContent = msg;
        }
        
        // Update the standard loader if present
        const loaderText = document.querySelector('#loader .loader-text');
        if (loaderText) {
            loaderText.textContent = msg;
        }
    }

    const socketInstance = new SeismicSocket();
    window.SeismicSocket = SeismicSocket;
    window.seismicSocket = socketInstance;
    window.updateProgress = updateProgress;

    window.addEventListener('beforeunload', () => {
        if (window.seismicSocket) window.seismicSocket.destroy();
    });
    window.addEventListener('pagehide', () => {
        if (window.seismicSocket) window.seismicSocket.destroy();
    });
})();
