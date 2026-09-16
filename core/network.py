import asyncio
import json
import logging
import socket
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

_osm_online_cache: dict[str, Any] = {'time': 0.0, 'status': False}

def is_osm_online() -> bool:
    """Quick cached check if OSM tile servers are reachable without blocking page generation."""
    now = time.time()
    if now - _osm_online_cache['time'] < 60.0:
        return bool(_osm_online_cache['status'])

    online = False
    try:
        # 1. Quick probe to raw IP (no DNS resolution overhead or timeout hang when offline)
        with socket.create_connection(("1.1.1.1", 53), timeout=0.4):
            online = True
    except OSError:
        online = False

    if online:
        # 2. Verify OSM tile server domain
        try:
            with socket.create_connection(("a.tile.openstreetmap.org", 443), timeout=0.5):
                online = True
        except OSError:
            online = False

    _osm_online_cache['time'] = now
    _osm_online_cache['status'] = online
    return online

class ConnectionManager:
    """Manages active WebSocket connections and broadcasting."""
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept connection and track it."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove connection from tracking."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict[str, Any], websocket: WebSocket) -> None:
        """Send message to a specific connection."""
        await websocket.send_json(message)

    async def broadcast(self, message: dict) -> None:
        """Broadcast message to all active connections."""
        stale: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Connection might be stale
                stale.append(connection)
        for dead in stale:
            if dead in self.active_connections:
                self.active_connections.remove(dead)

async def handle_websocket_messages(websocket: WebSocket, manager: ConnectionManager, api_ref: Any | None = None) -> None:
    """Handle incoming WebSocket messages and route them to the API bridge."""
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get("type")
            request_id = message.get("id")
            
            if msg_type == "ping":
                await manager.send_personal_message({"type": "pong", "id": request_id}, websocket)
            
            elif msg_type in ("get_cluster_update", "get_structural_planes", "get_animated_clustering", "auto_tune_time_window"):
                if not api_ref:
                    await manager.send_personal_message({"type": "rpc_response", "id": request_id, "error": "API bridge not ready"}, websocket)
                    continue
                p = message.get("params", {})
                if msg_type == "get_cluster_update":
                    result = await asyncio.to_thread(api_ref.get_cluster_update, p.get("method"), p.get("params"))
                elif msg_type == "get_structural_planes":
                    result = await asyncio.to_thread(api_ref.get_structural_planes, p.get("radius_km"), p.get("min_pts"), p.get("window_days"), p.get("anim_mode", "accumulation"), p.get("step_days", 7))
                elif msg_type == "auto_tune_time_window":
                    result = await asyncio.to_thread(api_ref.auto_tune_time_window)
                else:  # get_animated_clustering
                    result = await asyncio.to_thread(api_ref.get_animated_clustering, p.get("method"), p.get("params"), p.get("plane_step", 5))
                await manager.send_personal_message({"type": "rpc_response", "id": request_id, "result": result}, websocket)

    except (WebSocketDisconnect, ConnectionResetError, OSError):
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
        manager.disconnect(websocket)
