"""
WebSocket support for real-time candidate status updates.

Clients connect to /ws/{user_type}/{user_id} with a valid JWT token
passed as a query parameter (?token=...).

The server broadcasts events when candidate statuses change, compliance
evaluations complete, or TrustID tasks are updated.

Usage from other modules:
    from app.routes.websocket import broadcast_event
    await broadcast_event("candidate_status", {"candidate_id": "...", "status": "compliant"})
    # or synchronously:
    broadcast_event_sync("candidate_status", {"candidate_id": "...", "status": "compliant"})
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


# ── Connection Manager ───────────────────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections grouped by user type and user ID."""

    def __init__(self) -> None:
        # key: (user_type, user_id) -> list of WebSocket connections
        self._connections: dict[tuple[str, str], list[WebSocket]] = {}
        # key: user_type -> list of WebSocket connections (for broadcast to all of a type)
        self._type_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_type: str, user_id: str) -> None:
        await websocket.accept()
        key = (user_type, user_id)
        self._connections.setdefault(key, []).append(websocket)
        self._type_connections.setdefault(user_type, []).append(websocket)
        logger.info("WebSocket connected: %s/%s (total: %d)", user_type, user_id, self.count())

    def disconnect(self, websocket: WebSocket, user_type: str, user_id: str) -> None:
        key = (user_type, user_id)
        if key in self._connections:
            self._connections[key] = [c for c in self._connections[key] if c is not websocket]
            if not self._connections[key]:
                del self._connections[key]
        if user_type in self._type_connections:
            self._type_connections[user_type] = [
                c for c in self._type_connections[user_type] if c is not websocket
            ]
            if not self._type_connections[user_type]:
                del self._type_connections[user_type]
        logger.info("WebSocket disconnected: %s/%s (total: %d)", user_type, user_id, self.count())

    async def send_to_user(self, user_type: str, user_id: str, data: dict) -> int:
        """Send a message to a specific user. Returns number of connections reached."""
        key = (user_type, user_id)
        connections = self._connections.get(key, [])
        sent = 0
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(data)
                sent += 1
            except Exception:
                dead.append(ws)
        # Clean up dead connections
        for ws in dead:
            self.disconnect(ws, user_type, user_id)
        return sent

    async def broadcast_to_type(self, user_type: str, data: dict) -> int:
        """Broadcast to all connections of a given user type. Returns count."""
        connections = list(self._type_connections.get(user_type, []))
        sent = 0
        for ws in connections:
            try:
                await ws.send_json(data)
                sent += 1
            except Exception:
                pass  # individual disconnects handled on next message
        return sent

    async def broadcast_all(self, data: dict) -> int:
        """Broadcast to all connected clients."""
        sent = 0
        for user_type in list(self._type_connections.keys()):
            sent += await self.broadcast_to_type(user_type, data)
        return sent

    def count(self) -> int:
        return sum(len(conns) for conns in self._connections.values())

    def get_stats(self) -> dict:
        return {
            "total_connections": self.count(),
            "by_type": {
                ut: len(conns) for ut, conns in self._type_connections.items()
            },
        }


# Global connection manager instance
manager = ConnectionManager()


# ── WebSocket Endpoint ───────────────────────────────────────────────────────

@router.websocket("/ws/{user_type}/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_type: str,
    user_id: str,
    token: Optional[str] = Query(None),
):
    """WebSocket endpoint for real-time updates.

    Connect with: ws://host/ws/{user_type}/{user_id}?token=JWT_TOKEN
    """
    # Validate token
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return

    try:
        from app.utils.auth import decode_token
        payload = decode_token(token)
        if payload.get("sub") != user_id or payload.get("type") != user_type:
            await websocket.close(code=4003, reason="Token mismatch")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await manager.connect(websocket, user_type, user_id)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "user_type": user_type,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            # Handle ping/pong keepalive
            if data == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                # Echo back acknowledgement for any client messages
                try:
                    msg = json.loads(data)
                    await websocket.send_json({"type": "ack", "received": msg.get("type", "unknown")})
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "message": "Invalid JSON"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_type, user_id)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        manager.disconnect(websocket, user_type, user_id)


# ── Status Endpoint ──────────────────────────────────────────────────────────

@router.get("/api/ws/status")
async def ws_status():
    """Get WebSocket connection statistics."""
    return manager.get_stats()


# ── Broadcast Helpers (used by other modules) ────────────────────────────────

async def broadcast_event(event_type: str, data: dict, target_user_type: str | None = None) -> int:
    """Broadcast an event to connected WebSocket clients.

    Args:
        event_type: Type of event (e.g. 'candidate_status', 'trustid_update')
        data: Event payload
        target_user_type: If set, only broadcast to this user type

    Returns:
        Number of clients reached
    """
    message = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if target_user_type:
        return await manager.broadcast_to_type(target_user_type, message)
    return await manager.broadcast_all(message)


def broadcast_event_sync(event_type: str, data: dict, target_user_type: str | None = None) -> None:
    """Synchronous wrapper for broadcast_event. Safe to call from sync code.

    Schedules the broadcast on the running event loop if available,
    otherwise silently skips (e.g. in test or CLI contexts).
    """
    message = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        loop = asyncio.get_running_loop()
        if target_user_type:
            loop.create_task(manager.broadcast_to_type(target_user_type, message))
        else:
            loop.create_task(manager.broadcast_all(message))
    except RuntimeError:
        # No running event loop — skip broadcast
        logger.debug("No event loop available for WebSocket broadcast — skipping")
