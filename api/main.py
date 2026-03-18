"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import (
    BackgroundTasks, FastAPI, File, Form,
    HTTPException, Query, UploadFile,
    WebSocket, WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agents.super_agent import run_pipeline
from api.ws_manager import ws_manager
from schemas.models import (
    AgentStatus, SessionStatusResponse, StartSessionResponse,
)
from state.session_store import session_store
from utils.config import get_settings
from utils.logging import configure_logging

log = structlog.get_logger(__name__)
cfg = get_settings()


# Lifespan

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(cfg.log_level)
    log.info("app.starting", port=cfg.app_port)
    await session_store.connect(cfg.redis_url)
    yield
    await session_store.disconnect()
    log.info("app.stopped")


# App

app = FastAPI(
    title="SE POC",
    description=(
        "Orano Test v1.0"
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helpers

def _require_api_key() -> str:
    key = cfg.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    # For early API testing we don't hard-fail when the key is missing.
    # The downstream agents will fall back to lightweight mock behaviour.
    return key


async def _broadcast(session_id: str, payload: dict) -> None:
    """Broadcast + append event to session store."""
    await ws_manager.broadcast(session_id, payload)
    # Also store the event in session for polling clients
    from schemas.models import AgentEvent
    try:
        ev = AgentEvent.model_validate(payload)
        await session_store.append_event(session_id, ev)
    except Exception:
        pass  # never let event storage break the pipeline


async def _run_pipeline_task(
    session_id: str,
) -> None:
    """Background task wrapper — catches all unhandled exceptions."""
    try:
        await run_pipeline(
            session_id=session_id,
            broadcast=_broadcast,
            store=session_store,
        )
    except Exception as exc:
        log.error("background_task.unhandled", session_id=session_id, exc=str(exc))
        await session_store.mark_failed(session_id, str(exc))
        await ws_manager.broadcast(session_id, {
            "session_id": session_id,
            "agent": "super",
            "step": "unhandled_error",
            "status": "failed",
            "error": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# Health

@app.get("/health", tags=["meta"], summary="Health check")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active_ws_sessions": len(ws_manager.active_sessions()),
        "version": "2.0.0",
    }


# Session endpoints

@app.post(
    "/api/v1/sessions/start",
    response_model=StartSessionResponse,
    tags=["sessions"],
    summary="Start a new multi-agent session",
    status_code=202,
)
async def start_session(
    background_tasks: BackgroundTasks,
):
    """
    Start a new multi-agent session and immediately receive a session_id.
    Connect to ws_url for real-time progress.
    Poll status_url to check completion without WebSocket.
    """
    _require_api_key()

    session_id = str(uuid.uuid4())

    # Create session record in Redis before starting background task
    await session_store.create(
        sid=session_id,
    )

    background_tasks.add_task(
        _run_pipeline_task,
        session_id=session_id,
    )

    log.info("session.started", session_id=session_id)

    base = "/api/v1/sessions"
    return StartSessionResponse(
        session_id=session_id,
        ws_url=f"/ws/{session_id}",
        status_url=f"{base}/{session_id}/status",
        model_url=f"{base}/{session_id}/model",
        research_url=f"{base}/{session_id}/research",
        message=(
            "Pipeline started. Connect to ws_url for live progress "
            "or poll status_url."
        ),
    )


@app.get(
    "/api/v1/sessions/{session_id}/status",
    response_model=SessionStatusResponse,
    tags=["sessions"],
    summary="Poll session status",
)
async def get_status(session_id: str):
    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    return SessionStatusResponse(
        session_id=state.session_id,
        status=state.status.value,
        filename=state.filename,
        events_count=len(state.events),
        has_iso_model=state.iso_model is not None,
        has_research=state.research_result is not None,
        error=state.error,
        created_at=state.created_at,
        updated_at=state.updated_at,
    )


@app.get(
    "/api/v1/sessions/{session_id}/model",
    tags=["sessions"],
    summary="Get ISO 15926 structured model (available after Operational Agent completes)",
)
async def get_model(session_id: str):
    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    if state.iso_model is None:
        raise HTTPException(
            status_code=202,
            detail="ISO model not yet available — operational agent still running.",
        )
    return state.iso_model.model_dump()


@app.get(
    "/api/v1/sessions/{session_id}/research",
    tags=["sessions"],
    summary="Get research result — standards + technologies + gap analysis",
)
async def get_research(
    session_id: str,
    format: str = Query("full", description="full | summary | executive"),
):
    """
    format=full       → complete records + summary_table + executive_summary
    format=summary    → summary_table + executive_summary only (lighter payload)
    format=executive  → executive_summary only
    """
    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    if state.research_result is None:
        raise HTTPException(
            status_code=202,
            detail="Research results not yet available — research agent still running.",
        )

    r = state.research_result
    if format == "executive":
        return {
            "session_id": r.session_id,
            "generated_at": r.generated_at,
            "executive_summary": r.executive_summary.model_dump() if r.executive_summary else None,
        }
    elif format == "summary":
        return {
            "session_id": r.session_id,
            "generated_at": r.generated_at,
            "summary_table": [row.model_dump() for row in r.summary_table],
            "executive_summary": r.executive_summary.model_dump() if r.executive_summary else None,
        }
    else:
        return r.model_dump()


@app.get(
    "/api/v1/sessions/{session_id}/research/raw-records",
    tags=["sessions"],
    summary="Get raw per-requirement research records (debug view)",
)
async def get_research_raw_records(session_id: str):
    """
    Return the list of RequirementResearchRecord objects for this session
    without summary table or executive summary.
    """
    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    if state.research_result is None:
        raise HTTPException(
            status_code=202,
            detail="Research results not yet available — research agent still running.",
        )
    r = state.research_result
    return [rec.model_dump() for rec in r.records]


@app.get(
    "/api/v1/sessions/{session_id}/export",
    tags=["sessions"],
    summary="Export full session as JSON download",
)
async def export_session(session_id: str):
    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    return JSONResponse(
        content=state.model_dump(),
        headers={
            "Content-Disposition": f'attachment; filename="session_{session_id}.json"'
        },
    )


@app.get(
    "/api/v1/sessions/{session_id}/events",
    tags=["sessions"],
    summary="Get all agent progress events for this session",
)
async def get_events(session_id: str, agent: Optional[str] = Query(None)):
    """
    agent filter: 'super' | 'operational' | 'research'
    """
    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    events = state.events
    if agent:
        events = [e for e in events if e.agent.value == agent]
    return {
        "session_id": session_id,
        "total": len(events),
        "events": [e.to_ws() for e in events],
    }


@app.delete(
    "/api/v1/sessions/{session_id}",
    tags=["sessions"],
    summary="Delete a session",
)
async def delete_session(session_id: str):
    await session_store.delete(session_id)
    return {"message": f"Session {session_id} deleted."}


# WebSocket
# WebSocket
@app.websocket("/ws-test")
async def websocket_test(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"status": "ok"})
    await websocket.close()
    
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Real-time event stream for a pipeline session.

    On connect: server sends a 'connected' message and drains buffered events.

    Server → Client message format:
    {
      "session_id": "...",
      "agent": "super|operational|research",
      "step": "step_name",
      "status": "pending|running|completed|failed|cancelled",
      "payload": { ... } | null,
      "error": "..." | null,
      "timestamp": "ISO8601"
    }

    Client → Server messages:
      {"type": "ping"}    → {"type": "pong", "timestamp": "..."}
      {"type": "cancel"}  → cancels running session (best-effort)
      {"type": "status"}  → {"type": "status_reply", "status": "...", ...}
    """
    await ws_manager.connect(session_id, websocket)

    # Greet the client with current session state
    try:
        state = await session_store.get(session_id)
        await ws_manager.send_direct(session_id, websocket, {
            "type": "connected",
            "session_id": session_id,
            "status": state.status.value if state else "unknown",
            "has_iso_model": (state.iso_model is not None) if state else False,
            "has_research": (state.research_result is not None) if state else False,
            "events_buffered": len(state.events) if state else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        log.warning("ws.greeting_failed", session_id=session_id, exc=str(exc))

    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(), timeout=60.0
                )
            except asyncio.TimeoutError:
                # Send server-side ping to keep connection alive
                await ws_manager.send_direct(session_id, websocket, {
                    "type": "keepalive",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                continue

            msg_type = data.get("type", "")

            if msg_type == "ping":
                await ws_manager.send_direct(session_id, websocket, {
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            elif msg_type == "status":
                state = await session_store.get(session_id)
                await ws_manager.send_direct(session_id, websocket, {
                    "type": "status_reply",
                    "session_id": session_id,
                    "status": state.status.value if state else "unknown",
                    "has_iso_model": (state.iso_model is not None) if state else False,
                    "has_research": (state.research_result is not None) if state else False,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            elif msg_type == "cancel":
                state = await session_store.get(session_id)
                if state and state.status == AgentStatus.RUNNING:
                    await session_store.mark_failed(session_id, "Cancelled by client")
                    await ws_manager.broadcast(session_id, {
                        "session_id": session_id,
                        "agent": "super",
                        "step": "cancelled",
                        "status": "cancelled",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            else:
                await ws_manager.send_direct(session_id, websocket, {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type!r}",
                })

    except WebSocketDisconnect:
        log.info("ws.client_disconnected", session_id=session_id)
    except Exception as exc:
        log.warning("ws.error", session_id=session_id, exc=str(exc))
    finally:
        await ws_manager.disconnect(session_id, websocket)
