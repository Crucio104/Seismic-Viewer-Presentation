import asyncio
import atexit
import json
import logging
from pathlib import Path
import socket
import sys
import threading
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
import uvicorn
import webview
from fastapi import FastAPI, Response, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

def _json_default(obj: Any) -> Any:
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode('utf-8', errors='replace')
    if hasattr(obj, '__str__'):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

try:
    import orjson

    def _fast_dumps(obj: Any) -> bytes | str:
        try:
            return orjson.dumps(obj, option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NON_STR_KEYS)
        except Exception:
            return json.dumps(obj, separators=(',', ':'), default=_json_default)
except ImportError:
    def _fast_dumps(obj: Any) -> str:
        return json.dumps(obj, separators=(',', ':'), default=_json_default)

from core.bridge import Api
from core.config import (
    BASE_DIR, INDEX_REL, set_http_port, get_session_data,
    clear_session_data, get_viz_html, enforce_temp_dir_limit,
)
from core.loader import pack_seismic_binary
from core.network import ConnectionManager, handle_websocket_messages

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger("SeismicViewer")

if sys.platform == 'win32' and sys.version_info < (3, 14):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- Server Controller ---

class ServerController:
    """Encapsulates the FastAPI/uvicorn server lifecycle and thread management."""
    def __init__(self):
        self.server_thread: threading.Thread | None = None
        self.uvicorn_server: uvicorn.Server | None = None
        self.api_ref: Api | None = None
        self.port: int = 0

    def start(self, api_instance: Api) -> None:
        if self.server_thread is not None:
            return 

        self.api_ref = api_instance
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as temp_socket:
            temp_socket.bind(('127.0.0.1', 0))
            port = temp_socket.getsockname()[1]

        self.port = port
        set_http_port(port)
        app = _create_fastapi_app(self)

        config = uvicorn.Config(
            app, host="127.0.0.1", port=port,
            log_level="warning", access_log=False,
        )
        self.uvicorn_server = uvicorn.Server(config)
        self.server_thread = threading.Thread(target=self.uvicorn_server.run, daemon=True)
        self.server_thread.start()
        logger.info(f"FastAPI server running on port {port}")

    def stop(self) -> None:
        if self.uvicorn_server:
            try:
                self.uvicorn_server.should_exit = True
            except Exception as e:
                logger.debug(f"Error while requesting uvicorn shutdown: {e}")
            self.uvicorn_server = None
            self.server_thread = None

server_controller = ServerController()

# --- Route Handlers ---

async def get_data_handler(session_id: str) -> Response:
    """Serve session data as compressed JSON without blocking the async event loop."""
    data = get_session_data(session_id)
    if data is None:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    # Exclude non-JSON serializable binary buffers and heavy arrays transferred via /bin or unused in JS
    omit_keys = {
        'binary_buffer', 'longitude', 'latitude', 'magnitude', 'depth', 'dates_num',
        'lon', 'lat', 'mag', 'dep', 'dnum', 'visual_pack', 'hover', 'depth_is_missing'
    }
    has_orjson = 'orjson' in sys.modules
    if has_orjson:
        json_data = {k: v for k, v in data.items() if k not in omit_keys and not isinstance(v, bytes)}
    else:
        json_data = {
            k: (v.tolist() if isinstance(v, np.ndarray) else v)
            for k, v in data.items()
            if k not in omit_keys and not isinstance(v, bytes)
        }
    content = await asyncio.to_thread(_fast_dumps, json_data)
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
    """Serve numerical data as binary Float32 buffer without blocking the async event loop."""
    data = get_session_data(session_id)
    if data is None:
        return Response(status_code=404)
    
    try:
        buffer = await asyncio.to_thread(pack_seismic_binary, data)
        return Response(
            content=buffer,
            media_type="application/octet-stream",
            headers={"Cache-Control": "no-store"}
        )
    except Exception as e:
        logger.error(f"Binary Packing Error: {e}")
        return Response(status_code=500)

# --- App Factory ---

def _create_fastapi_app(controller: ServerController) -> FastAPI:
    """Build the FastAPI application."""
    manager = ConnectionManager()
    if controller.api_ref:
        controller.api_ref.set_socket_manager(manager, None)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loop = asyncio.get_running_loop()

        def _quiet_exception_handler(l, context):
            exc = context.get("exception")
            if isinstance(exc, (ConnectionResetError, OSError)):
                return
            msg = context.get("message", "")
            if "_call_connection_lost" in msg or "ConnectionResetError" in msg:
                return
            l.default_exception_handler(context)

        loop.set_exception_handler(_quiet_exception_handler)
        if controller.api_ref:
            controller.api_ref.set_socket_manager(manager, loop)
        yield

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # WebSocket
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        await handle_websocket_messages(websocket, manager, controller.api_ref)

    # API Endpoints
    app.get("/api/data/{session_id}")(get_data_handler)
    app.get("/viz/{viz_id}")(get_viz_handler)
    app.get("/api/data/{session_id}/bin")(get_data_binary_handler)

    # Static files with client-side caching & gzip pre-compression serving
    class CachedStaticFiles(StaticFiles):
        def file_response(self, *args, **kwargs) -> Response:
            full_path = args[0] if args else kwargs.get("full_path")
            scope = kwargs.get("scope")
            headers = dict(scope.get("headers", [])) if scope else {}
            accept_enc = headers.get(b"accept-encoding", b"").decode("latin1", errors="ignore")

            if full_path and "gzip" in accept_enc:
                gz_path = f"{full_path}.gz"
                if Path(gz_path).is_file():
                    resp = FileResponse(gz_path, headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})
                    resp.headers["Cache-Control"] = "public, max-age=86400"
                    if str(full_path).endswith('.js'):
                        resp.media_type = "application/javascript"
                    elif str(full_path).endswith('.css'):
                        resp.media_type = "text/css"
                    return resp

            resp = super().file_response(*args, **kwargs)
            resp.headers["Cache-Control"] = "public, max-age=86400"
            return resp

    assets_dir = BASE_DIR / 'assets'
    app.mount("/assets", CachedStaticFiles(directory=str(assets_dir), html=True), name="assets")

    return app

# --- Cleanup & Entry Point ---

def _cleanup() -> None:
    server_controller.stop()
    clear_session_data()

atexit.register(_cleanup)

def main() -> None:
    enforce_temp_dir_limit()
    _win_holder: list[webview.Window] = []
    def win_ref() -> webview.Window: return _win_holder[0]

    icon_png = BASE_DIR / 'assets' / 'app_icon.png'
    icon_ico = BASE_DIR / 'assets' / 'app_icon.ico'

    if sys.platform == 'win32':
        if not icon_ico.exists() and icon_png.exists():
            try:
                from PIL import Image
                img = Image.open(icon_png)
                img.save(icon_ico, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            except Exception as e:
                logger.debug(f"Could not generate .ico from app_icon.png: {e}")
        icon_str = str(icon_ico.resolve()) if icon_ico.exists() else None
    else:
        icon_target = icon_png if icon_png.exists() else icon_ico
        icon_str = str(icon_target.resolve()) if icon_target.exists() else None

    # On macOS, proactively configure the Dock icon via AppKit
    if sys.platform == 'darwin' and icon_png.exists():
        try:
            import AppKit
            ns_image = AppKit.NSImage.alloc().initByReferencingFile_(str(icon_png.resolve()))
            if ns_image and ns_image.isValid():
                AppKit.NSApplication.sharedApplication().setApplicationIconImage_(ns_image)
        except Exception as e:
            logger.debug(f"Could not set macOS Dock icon via AppKit: {e}")

    api = Api(win_ref)
    server_controller.start(api)
    port = server_controller.port
    start_url = f"http://127.0.0.1:{port}/assets/index.html" if port > 0 else (BASE_DIR / INDEX_REL).absolute().as_uri()
    
    window = webview.create_window(
        'Seismic Viewer', url=start_url, js_api=api,
        width=1150, height=850, min_size=(1000, 750),
        background_color='#050510'
    )
    _win_holder.append(window)

    window.events.closing += lambda: logger.info("Window closing...")

    logger.info("Starting Seismic Viewer…")
    try:
        webview.start(debug=False, icon=icon_str)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.warning(f"Failed to start with custom icon ({e}), falling back to default icon...")
        try:
            webview.start(debug=False)
        except KeyboardInterrupt:
            pass

if __name__ == '__main__':
    main()
