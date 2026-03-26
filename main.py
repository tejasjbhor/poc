"""Optional FastAPI over the same graph. Prefer run_chat.cmd / run_watch.cmd locally."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

for _env_path in [
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent / ".env",
]:
    if _env_path.exists():
        load_dotenv(_env_path)
        break

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph import apply_feedback, build_graph, get_state, send_message
from llm_config import get_llm_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting: compiling graph (MemorySaver)")
    app.state.graph = build_graph(checkpointer=None)
    logger.info("Graph ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Super Agent API",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter()

#class1 
class CreateSessionResponse(BaseModel):
    session_id: str

#class4
class MessageIn(BaseModel):
    text: str

#class3
class MessageOut(BaseModel):
    user: str
    assistant: str
    sa_state: dict

#class4
class CardFeedback(BaseModel):
    action: str
    suggestion_id: str | None = None


def _extract_sa_state(raw_state: dict) -> dict:
    return {
        "next_agent": raw_state.get("next_agent") or "",
        "session_goal": raw_state.get("session_goal") or "",
        "goal_progress": raw_state.get("goal_progress") or "",
        "inferred_domain": raw_state.get("sa_inferred_domain") or "",
        "inferred_task": raw_state.get("sa_inferred_task") or "",
        "phase": raw_state.get("sa_phase") or "",
        "thoughts": raw_state.get("sa_thoughts") or [],
        "checklist": raw_state.get("sa_checklist") or [],
        "card": raw_state.get("sa_card"),
        "active_agent": raw_state.get("active_agent") or "",
        "agents": raw_state.get("agents") or {},
        "buffer_pending": [
            b
            for b in (raw_state.get("sa_readiness_buffer") or [])
            if not b.get("fired")
        ],
    }


def _extract_agent_reply(raw_state: dict) -> str:
    messages = raw_state.get("messages") or []
    for msg in reversed(messages):
        if getattr(msg, "type", "") == "ai":
            return getattr(msg, "content", "")
    return ""


def _extract_messages(raw_state: dict) -> list[dict]:
    result = []
    for msg in raw_state.get("messages") or []:
        msg_type = getattr(msg, "type", "")
        if msg_type == "human":
            result.append({"role": "user", "content": getattr(msg, "content", "")})
        elif msg_type == "ai":
            agent = (getattr(msg, "additional_kwargs", {}) or {}).get("agent", "")
            result.append(
                {
                    "role": "assistant",
                    "content": getattr(msg, "content", ""),
                    "agent": agent,
                }
            )
    return result


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session():
    sid = str(uuid.uuid4())
    logger.info("Session created: %s", sid)
    return CreateSessionResponse(session_id=sid)


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    graph = app.state.graph
    state = await get_state(graph, session_id)
    return {"messages": _extract_messages(state)}


@router.get("/sessions/{session_id}/sa")
async def get_sa_state(session_id: str):
    graph = app.state.graph
    state = await get_state(graph, session_id)
    return _extract_sa_state(state)


@router.post("/sessions/{session_id}/message", response_model=MessageOut)
async def post_message(session_id: str, body: MessageIn):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Message cannot be empty.")

    graph = app.state.graph
    await send_message(graph, session_id, text)
    final_state = await get_state(graph, session_id)

    assistant_reply = _extract_agent_reply(final_state)
    sa_state = _extract_sa_state(final_state)

    logger.info(
        "Session %s: reply=%d chars  domain='%s'  card=%s  buffer_pending=%d",
        session_id,
        len(assistant_reply),
        sa_state.get("inferred_domain", "?"),
        sa_state.get("card") is not None,
        len(sa_state.get("buffer_pending") or []),
    )

    return MessageOut(
        user=text,
        assistant=assistant_reply,
        sa_state=sa_state,
    )


@router.post("/sessions/{session_id}/sa/feedback")
async def sa_feedback(session_id: str, body: CardFeedback):
    graph = app.state.graph
    await apply_feedback(graph, session_id, body.action, body.suggestion_id)
    final_state = await get_state(graph, session_id)

    sa_state = _extract_sa_state(final_state)
    logger.info(
        "SA feedback: session=%s action=%s suggestion=%s",
        session_id,
        body.action,
        body.suggestion_id,
    )
    return {"ok": True, "action": body.action, "sa_state": sa_state}


@app.get("/")
def root():
    return {
        "service": "super-agent-platform",
        "version": "3.0.0",
        "note": "run_chat.cmd + run_watch.cmd for CLI.", #we didnt have redis or wesocket yet
        "docs": "/docs",
        "endpoints": {
            "create_session": "POST /api/sessions",
            "send_message": "POST /api/sessions/{id}/message",
            "get_messages": "GET  /api/sessions/{id}/messages",
            "get_sa_state": "GET  /api/sessions/{id}/sa",
            "sa_feedback": "POST /api/sessions/{id}/sa/feedback",
            "health": "GET  /health",
        },
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "graph": "compiled",
        "llm_configured": bool(get_llm_api_key()),
        "checkpointer": "MemorySaver (in-process only)",
    }


app.include_router(router, prefix="/api")
app.include_router(router)
