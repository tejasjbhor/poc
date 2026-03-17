"""WebSocket connection manager."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import Deque, Dict, List

from fastapi import WebSocket
import structlog

log = structlog.get_logger(__name__)

# Buffer size for per-session events
BUFFER_SIZE = 500


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: Dict[str, List[WebSocket]] = defaultdict(list)
        self._buffers: Dict[str, Deque[dict]] = defaultdict(
            lambda: deque(maxlen=BUFFER_SIZE)
        )
        self._lock = asyncio.Lock()

    # ── connection lifecycle ──────────────────────────────────────────────

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections[session_id].append(ws)
        log.info("ws.connected", session_id=session_id,
                 clients=len(self._connections[session_id]))

        # Drain buffer to late-joining client
        buffered = list(self._buffers.get(session_id, []))
        for msg in buffered:
            try:
                await ws.send_json(msg)
            except Exception:
                break

    async def disconnect(self, session_id: str, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(session_id, [])
            if ws in conns:
                conns.remove(ws)
            if not conns:
                self._connections.pop(session_id, None)
        log.info("ws.disconnected", session_id=session_id)

    # ── broadcast ─────────────────────────────────────────────────────────

    async def broadcast(self, session_id: str, payload: dict) -> None:
        """Broadcast to all connected clients; buffer for late joiners."""
        # Always buffer
        self._buffers[session_id].append(payload)

        async with self._lock:
            conns = list(self._connections.get(session_id, []))

        if not conns:
            return

        dead: List[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception as exc:
                log.debug("ws.send_failed", exc=str(exc))
                dead.append(ws)

        if dead:
            async with self._lock:
                for d in dead:
                    try:
                        self._connections[session_id].remove(d)
                    except ValueError:
                        pass

    async def send_direct(self, session_id: str, ws: WebSocket,
                          payload: dict) -> None:
        """Send to one specific WebSocket only (not buffered)."""
        try:
            await ws.send_json(payload)
        except Exception as exc:
            log.debug("ws.direct_send_failed", exc=str(exc))
            await self.disconnect(session_id, ws)

    # ── helpers ───────────────────────────────────────────────────────────

    def active_sessions(self) -> List[str]:
        return list(self._connections.keys())

    def client_count(self, session_id: str) -> int:
        return len(self._connections.get(session_id, []))


ws_manager = WebSocketManager()
