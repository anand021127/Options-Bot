"""
WebSocket Manager
Manages client connections and broadcasts real-time updates.
All connected dashboards receive the same event stream.
"""

import json
import asyncio
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

ws_router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)
        logger.info(f"WS client connected. Total: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)
        logger.info(f"WS client disconnected. Total: {len(self.active)}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        if not self.active:
            return
        data = json.dumps(message)
        dead = set()
        for ws in list(self.active):
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.active.discard(ws)

    async def send_personal(self, ws: WebSocket, message: dict):
        try:
            await ws.send_text(json.dumps(message))
        except Exception as e:
            logger.warning(f"Personal send failed: {e}")


manager = ConnectionManager()


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # Send welcome / current state
    await manager.send_personal(websocket, {
        "event": "connected",
        "data": {"message": "Connected to Options Trading Bot"}
    })
    try:
        while True:
            # Keep connection alive; client can send pings
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await manager.send_personal(websocket, {"event": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS error: {e}")
        manager.disconnect(websocket)


async def broadcast_to_all(message: dict):
    """Exposed to bot_engine to broadcast events."""
    await manager.broadcast(message)
