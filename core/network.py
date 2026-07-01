import logging
import asyncio
import json
from typing import Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages active WebSocket connections and broadcasting."""
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept connection and track it."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove connection from tracking."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to a specific connection."""
        await websocket.send_json(message)

    async def broadcast(self, message: dict) -> None:
        """Broadcast message to all active connections."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Connection might be stale
                pass

async def handle_websocket_messages(websocket: WebSocket, manager: ConnectionManager, api_ref: Any, loop: Any):
    """Handle incoming WebSocket messages and route them to the API bridge."""
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get("type")
            request_id = message.get("id")
            
            if msg_type == "ping":
                await manager.send_personal_message({"type": "pong", "id": request_id}, websocket)
            
            elif msg_type == "get_cluster_update":
                p = message.get("params", {})
                # CPU-bound clustering should run in a thread
                result = await asyncio.to_thread(api_ref.get_cluster_update, p.get("method"), p.get("params"))
                await manager.send_personal_message({"type": "rpc_response", "id": request_id, "result": result}, websocket)

            elif msg_type == "get_structural_planes":
                p = message.get("params", {})
                result = await asyncio.to_thread(api_ref.get_structural_planes, p.get("radius_km"), p.get("min_pts"), p.get("window_days"), p.get("anim_mode", "accumulation"), p.get("step_days", 7))
                await manager.send_personal_message({"type": "rpc_response", "id": request_id, "result": result}, websocket)

            elif msg_type == "get_animated_clustering":
                p = message.get("params", {})
                result = await asyncio.to_thread(api_ref.get_animated_clustering, p.get("method"), p.get("params"), p.get("plane_step", 5))
                await manager.send_personal_message({"type": "rpc_response", "id": request_id, "result": result}, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
        manager.disconnect(websocket)
