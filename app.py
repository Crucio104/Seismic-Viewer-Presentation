import threading
import atexit
import webview
import logging
import json
import asyncio
import socket
import numpy as np
import uvicorn
from typing import Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response, HTMLResponse
from starlette.middleware.gzip import GZipMiddleware

# ─── Logging Setup ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("SeismicViewer")

# ─── Core Imports ────────────────────────────────────────────────────
from core.config import (
    BASE_DIR, INDEX_REL, set_http_port, get_session_data, 
    clear_session_data, get_viz_html
)
from core.bridge import Api

# ─── FastAPI Server ─────────────────────────────────────────────────
_server_thread: threading.Thread | None = None
_uvicorn_server: Any = None
_uvicorn_loop: Any = None
_api_ref: Any = None

def _create_fastapi_app() -> Any:
    """Build the FastAPI application with static file serving and API endpoints."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    # Capture the loop for bridge communication
    global _uvicorn_loop
    try:
        _uvicorn_loop = asyncio.get_event_loop()
    except Exception:
        _uvicorn_loop = None

    # ── WebSocket Management ──
    class ConnectionManager:
        def __init__(self) -> None:
            self.active_connections: list[WebSocket] = []

        async def connect(self, websocket: WebSocket) -> None:
            await websocket.accept()
            self.active_connections.append(websocket)

        def disconnect(self, websocket: WebSocket):
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

        async def send_personal_message(self, message: dict, websocket: WebSocket):
            await websocket.send_json(message)

        async def broadcast(self, message: dict) -> None:
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

    manager = ConnectionManager()
    if _api_ref:
        _api_ref.set_socket_manager(manager, _uvicorn_loop)

    # GZip compression for all responses > 500 bytes
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # ── WebSocket Endpoint ──
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                msg_type = message.get("type")
                request_id = message.get("id")
                
                # Route messages to bridge if needed
                if msg_type == "ping":
                    await manager.send_personal_message({"type": "pong", "id": request_id}, websocket)
                
                elif msg_type == "get_cluster_update":
                    p = message.get("params", {})
                    # Recalculate clusters in a separate thread (CPU bound)
                    result = await asyncio.to_thread(_api_ref.get_cluster_update, p.get("method"), p.get("params"))
                    await manager.send_personal_message({"type": "rpc_response", "id": request_id, "result": result}, websocket)

                elif msg_type == "get_structural_planes":
                    p = message.get("params", {})
                    # Process blocking calls in a thread to keep the event loop responsive
                    result = await asyncio.to_thread(_api_ref.get_structural_planes, p.get("radius_km"), p.get("min_pts"), p.get("window_days"))
                    await manager.send_personal_message({"type": "rpc_response", "id": request_id, "result": result}, websocket)

        except WebSocketDisconnect:
            manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket Error: {e}")
            manager.disconnect(websocket)

    # ── API endpoint: serve session data as compressed JSON ──
    @app.get("/api/data/{session_id}")
    async def get_data(session_id: str) -> Response:
        data = get_session_data(session_id)
        if data is None:
            return JSONResponse({"error": "Session not found"}, status_code=404)
        content = json.dumps(data, separators=(',', ':'))
        return Response(
            content=content,
            media_type="application/json",
            headers={"Cache-Control": "no-store"}
        )

    # ── API endpoint: serve HTML visualization from memory ──
    @app.get("/viz/{viz_id}")
    async def get_viz(viz_id: str) -> HTMLResponse:
        html = get_viz_html(viz_id)
        if html is None:
            return HTMLResponse("<h1>View expired or not found</h1>", status_code=404)
        return HTMLResponse(content=html)

    # ── API endpoint: serve numerical data as binary Float32 buffer ──
    @app.get("/api/data/{session_id}/bin")
    async def get_data_binary(session_id: str) -> Response:
        data = get_session_data(session_id)
        if data is None:
            return Response(status_code=404)
        
        try:
            # Flexible key mapping for both static and animated views
            lon_key = 'longitude' if 'longitude' in data else 'lon'
            lat_key = 'latitude' if 'latitude' in data else 'lat'
            mag_key = 'magnitude' if 'magnitude' in data else 'mag'
            dep_key = 'depth' if 'depth' in data else 'dep'
            dnum_key = 'dates_num' if 'dates_num' in data else 'dnum'

            # Ensure all keys exist and have values, otherwise fallback to zeros
            count = len(data.get(lon_key, []))
            
            def get_f32_array(key, length):
                arr = data.get(key)
                if arr is None or len(arr) == 0:
                    return np.zeros(length, dtype=np.float32)
                return np.array(arr, dtype=np.float32)

            lon = get_f32_array(lon_key, count)
            lat = get_f32_array(lat_key, count)
            mag = get_f32_array(mag_key, count)
            dep = get_f32_array(dep_key, count)
            dnum = get_f32_array(dnum_key, count)
            
            # Optional: Clustering labels
            cluster = data.get('cluster', [])
            if len(cluster) > 0:
                cluster_arr = np.array(cluster, dtype=np.float32)
            else:
                cluster_arr = np.zeros(0, dtype=np.float32)

            count_arr = np.array([count, len(cluster_arr)], dtype=np.float32)
            
            buffer = b"".join([
                count_arr.tobytes(), # Now 8 bytes: [N_points, N_clusters]
                lon.tobytes(),
                lat.tobytes(),
                mag.tobytes(),
                dep.tobytes(),
                dnum.tobytes(),
                cluster_arr.tobytes()
            ])
            
            return Response(
                content=buffer,
                media_type="application/octet-stream",
                headers={"Cache-Control": "no-store"}
            )
        except Exception as e:
            logger.error(f"Binary Packing Error: {e}")
            return Response(status_code=500)

    # ── Static file mounts ──
    assets_dir = BASE_DIR / 'assets'
    app.mount("/assets", StaticFiles(directory=str(assets_dir), html=True), name="assets")

    return app


def _start_http_server(api_instance: Any = None) -> None:
    """Start the FastAPI/Uvicorn server in a background thread."""
    global _server_thread, _uvicorn_server, _api_ref
    if _server_thread is not None:
        return 

    _api_ref = api_instance
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]

    set_http_port(port)

    app = _create_fastapi_app()

    config = uvicorn.Config(
        app, host="127.0.0.1", port=port,
        log_level="warning", access_log=False,
    )
    _uvicorn_server = uvicorn.Server(config)

    _server_thread = threading.Thread(target=_uvicorn_server.run, daemon=True)
    _server_thread.start()
    logger.info(f"FastAPI server: http://127.0.0.1:{port}")


def _stop_http_server() -> None:
    """Signal the Uvicorn server to shut down."""
    global _uvicorn_server, _server_thread
    if _uvicorn_server:
        try:
            _uvicorn_server.should_exit = True
        except Exception:
            pass
        _uvicorn_server = None
        _server_thread = None


# ─── Cleanup ────────────────────────────────────────────────────────

def _cleanup() -> None:
    """Fast cleanup: stop server and clear memory."""
    try:
        _stop_http_server()
        clear_session_data()
    except Exception:
        pass

atexit.register(_cleanup)


# ─── Entry point ─────────────────────────────────────────────────────

def main() -> None:
    _win_holder: list[webview.Window] = []

    def win_ref() -> webview.Window:
        return _win_holder[0]

    api = Api(win_ref)

    abs_index = (BASE_DIR / INDEX_REL).absolute()
    start_url = abs_index.as_uri()
    window = webview.create_window(
        'Seismic Viewer',
        url=start_url,
        js_api=api,
        width=1150,
        height=850,
        min_size=(1000, 750),
        background_color='#050510'
    )
    _win_holder.append(window)

    def on_closing() -> bool:
        logger.info("Window closing...")
        return True

    if window is not None:
        window.events.closing += on_closing

    logger.info("Starting Seismic Viewer…")
    try:
        # Pass api to server
        webview.start(lambda: _start_http_server(api), debug=False)
    except KeyboardInterrupt:
        pass
    
    logger.info("Window closed. Freeing terminal...")

if __name__ == '__main__':
    main()
