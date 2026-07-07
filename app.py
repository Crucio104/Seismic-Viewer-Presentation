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
from fastapi import FastAPI, WebSocket, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.middleware.gzip import GZipMiddleware

# Core Imports
from core.config import (
    BASE_DIR, INDEX_REL, set_http_port, get_session_data, 
    clear_session_data, get_viz_html
)
from core.bridge import Api
from core.network import ConnectionManager, handle_websocket_messages

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("SeismicViewer")

# --- Global State ---
_server_thread: threading.Thread | None = None
_uvicorn_server: uvicorn.Server | None = None
_uvicorn_loop: asyncio.AbstractEventLoop | None = None
_api_ref: Api | None = None

# --- Route Handlers ---

async def get_data_handler(session_id: str) -> Response:
    """Serve session data as compressed JSON."""
    data = get_session_data(session_id)
    if data is None:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    content = json.dumps(data, separators=(',', ':'))
    return Response(
        content=content,
        media_type="application/json",
        headers={"Cache-Control": "no-store"}
    )

async def get_viz_handler(viz_id: str) -> HTMLResponse:
    """Serve HTML visualization from memory."""
    html = get_viz_html(viz_id)
    if html is None:
        return HTMLResponse("<h1>View expired or not found</h1>", status_code=404)
    return HTMLResponse(content=html)

async def get_data_binary_handler(session_id: str) -> Response:
    """Serve numerical data as binary Float32 buffer for performance."""
    data = get_session_data(session_id)
    if data is None:
        return Response(status_code=404)
    
    try:
        buffer = pack_seismic_binary(data)
        return Response(
            content=buffer,
            media_type="application/octet-stream",
            headers={"Cache-Control": "no-store"}
        )
    except Exception as e:
        logger.error(f"Binary Packing Error: {e}")
        return Response(status_code=500)

def pack_seismic_binary(data: dict[str, Any]) -> bytes:
    """Pack seismic dictionary data into a compact binary Float32 buffer."""
    # Canonical key mapping
    lon_key = 'longitude' if 'longitude' in data else 'lon'
    lat_key = 'latitude' if 'latitude' in data else 'lat'
    mag_key = 'magnitude' if 'magnitude' in data else 'mag'
    dep_key = 'depth' if 'depth' in data else 'dep'
    dnum_key = 'dates_num' if 'dates_num' in data else 'dnum'

    count = len(data.get(lon_key, []))
    
    def _to_f32_bytes(key: str, length: int) -> bytes:
        arr = data.get(key)
        if arr is None or len(arr) == 0:
            return np.zeros(length, dtype=np.float32).tobytes()
        return np.array(arr, dtype=np.float32).tobytes()

    cluster = data.get('cluster', [])
    cluster_bytes = np.array(cluster, dtype=np.float32).tobytes() if cluster else b""

    return b"".join([
        np.array([count, len(cluster)], dtype=np.float32).tobytes(),
        _to_f32_bytes(lon_key, count),
        _to_f32_bytes(lat_key, count),
        _to_f32_bytes(mag_key, count),
        _to_f32_bytes(dep_key, count),
        _to_f32_bytes(dnum_key, count),
        cluster_bytes
    ])

# --- App Factory ---

def _create_fastapi_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    global _uvicorn_loop
    try:
        _uvicorn_loop = asyncio.get_event_loop()
    except Exception:
        _uvicorn_loop = None

    manager = ConnectionManager()
    if _api_ref:
        _api_ref.set_socket_manager(manager, _uvicorn_loop)

    app.add_middleware(GZipMiddleware, minimum_size=500)

    # WebSocket
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        await handle_websocket_messages(websocket, manager, _api_ref, _uvicorn_loop)

    # API Endpoints
    app.get("/api/data/{session_id}")(get_data_handler)
    app.get("/viz/{viz_id}")(get_viz_handler)
    app.get("/api/data/{session_id}/bin")(get_data_binary_handler)

    # Static files
    assets_dir = BASE_DIR / 'assets'
    app.mount("/assets", StaticFiles(directory=str(assets_dir), html=True), name="assets")

    return app

# --- Server Control ---

def _start_http_server(api_instance: Api | None = None) -> None:
    """Start the FastAPI server in a background thread."""
    global _server_thread, _uvicorn_server, _api_ref
    if _server_thread is not None:
        return 

    _api_ref = api_instance
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as temp_socket:
        temp_socket.bind(('127.0.0.1', 0))
        port = temp_socket.getsockname()[1]

    set_http_port(port)
    app = _create_fastapi_app()

    config = uvicorn.Config(
        app, host="127.0.0.1", port=port,
        log_level="warning", access_log=False,
    )
    _uvicorn_server = uvicorn.Server(config)

    _server_thread = threading.Thread(target=_uvicorn_server.run, daemon=True)
    _server_thread.start()
    logger.info(f"FastAPI server running on port {port}")

def _stop_http_server() -> None:
    """Shut down the server."""
    global _uvicorn_server, _server_thread
    if _uvicorn_server:
        try:
            _uvicorn_server.should_exit = True
        except Exception:
            pass
        _uvicorn_server = None
        _server_thread = None

# --- Cleanup & Entry Point ---

def _cleanup() -> None:
    _stop_http_server()
    clear_session_data()

atexit.register(_cleanup)

def main() -> None:
    _win_holder: list[webview.Window] = []
    def win_ref() -> webview.Window: return _win_holder[0]

    api = Api(win_ref)
    start_url = (BASE_DIR / INDEX_REL).absolute().as_uri()
    
    window = webview.create_window(
        'Seismic Viewer', url=start_url, js_api=api,
        width=1150, height=850, min_size=(1000, 750),
        background_color='#050510'
    )
    _win_holder.append(window)

    window.events.closing += lambda: logger.info("Window closing...")

    logger.info("Starting Seismic Viewer…")
    try:
        webview.start(lambda: _start_http_server(api), debug=False)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
