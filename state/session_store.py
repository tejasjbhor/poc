"""Session storage using Redis with in-memory fallback."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional

import structlog

from schemas.models import AgentEvent, AgentStatus, SessionState

log = structlog.get_logger(__name__)

SESSION_TTL = 14400   # 4 hours


class SessionStore:
    def __init__(self) -> None:
        self._redis = None
        self._fallback: Dict[str, str] = {}   # in-memory if Redis unavailable
        self._lock = asyncio.Lock()

    # Lifecycle

    async def connect(self, redis_url: str) -> None:
        try:
            import redis.asyncio as aioredis
            self._redis = await aioredis.from_url(
                redis_url, encoding="utf-8", decode_responses=True
            )
            await self._redis.ping()
            log.info("redis.connected", url=redis_url)
        except Exception as exc:
            log.warning("redis.unavailable", exc=str(exc),
                        note="Using in-memory fallback — state lost on restart")
            self._redis = None

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.aclose()

    # Raw storage

    def _key(self, sid: str) -> str:
        return f"mas:session:{sid}"

    async def _raw_get(self, sid: str) -> Optional[str]:
        k = self._key(sid)
        if self._redis:
            return await self._redis.get(k)
        return self._fallback.get(k)

    async def _raw_set(self, sid: str, data: str) -> None:
        k = self._key(sid)
        if self._redis:
            await self._redis.set(k, data, ex=SESSION_TTL)
        else:
            self._fallback[k] = data

    async def _raw_del(self, sid: str) -> None:
        k = self._key(sid)
        if self._redis:
            await self._redis.delete(k)
        else:
            self._fallback.pop(k, None)

    # Public API

    async def create(self, sid: str, filename: str = "", domain_context: str = "",) -> SessionState:
        state = SessionState(
            session_id=sid,
            status=AgentStatus.PENDING,
            filename=filename,
            domain_context=domain_context,
        )
        await self._raw_set(sid, state.model_dump_json())
        log.info("session.created", session_id=sid)
        return state

    async def get(self, sid: str) -> Optional[SessionState]:
        raw = await self._raw_get(sid)
        if not raw:
            return None
        return SessionState.model_validate_json(raw)

    async def save(self, state: SessionState) -> None:
        state.updated_at = datetime.now(timezone.utc).isoformat()
        await self._raw_set(state.session_id, state.model_dump_json())

    async def append_event(self, sid: str, event: AgentEvent) -> None:
        """Atomically append an event and update status."""
        async with self._lock:
            state = await self.get(sid)
            if not state:
                log.warning("session.not_found", session_id=sid)
                return
            state.events.append(event)
            # Promote session status when terminal
            if event.status in (AgentStatus.FAILED, AgentStatus.CANCELLED):
                state.status = event.status
            elif event.status == AgentStatus.RUNNING and state.status == AgentStatus.PENDING:
                state.status = AgentStatus.RUNNING
            await self.save(state)

    async def set_iso_model(self, sid: str, model) -> None:
        async with self._lock:
            state = await self.get(sid)
            if not state:
                return
            state.iso_model = model
            await self.save(state)

    async def set_research_result(self, sid: str, result) -> None:
        async with self._lock:
            state = await self.get(sid)
            if not state:
                return
            state.research_result = result
            state.status = AgentStatus.COMPLETED
            await self.save(state)

    async def mark_failed(self, sid: str, error: str) -> None:
        async with self._lock:
            state = await self.get(sid)
            if not state:
                return
            state.status = AgentStatus.FAILED
            state.error = error
            await self.save(state)

    async def mark_completed(self, sid: str) -> None:
        async with self._lock:
            state = await self.get(sid)
            if not state:
                return
            state.status = AgentStatus.COMPLETED
            await self.save(state)

    async def delete(self, sid: str) -> None:
        await self._raw_del(sid)


# Module-level singleton
session_store = SessionStore()
