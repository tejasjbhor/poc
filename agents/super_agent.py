"""Super agent orchestration logic."""

from __future__ import annotations

import json
from pathlib import Path
import traceback
from typing import Callable, Coroutine

import structlog
import asyncio

from state.session_store import session_file_queues
from agents.operational_agent import run_operational_agent
from agents.research_agent import run_research_agent
from schemas.models import AgentEvent, AgentName, AgentStatus, SessionState



## Need to add dynalic state change , funtion call ..may be no need ( dicuss with ali)

from state.session_store import SessionStore

log = structlog.get_logger(__name__)

BroadcastFn = Callable[[str, dict], Coroutine]


async def run_pipeline(
    session_id: str,
    broadcast: BroadcastFn,
    store: SessionStore,
) -> SessionState:
    """
    Full orchestration pipeline.
    Returns the final SessionState regardless of success/failure.
    Never raises — all errors are caught, persisted, and broadcast.
    """

    def _ev(step: str, status: AgentStatus, payload=None, error=None, agent: AgentName = AgentName.SUPER,):
        return AgentEvent(
            session_id=session_id, agent=agent,
            step=step, status=status, payload=payload, error=error,
        ).to_ws()

    # Step 1: signal start
    await broadcast(session_id, _ev(
        agent=AgentName.SUPER,
        step="super_agent_started",
        status=AgentStatus.RUNNING,
        payload={
        "note": "Super Agent Started",
        "session_id": session_id,
        },
    ))

    # 1. Create queue for user file input
    # Before running the operational agent:
    if session_id not in session_file_queues:
        session_file_queues[session_id] = asyncio.Queue()

    # Step 2: run operational agent
    try:
        iso_model = await run_operational_agent(
            session_id=session_id,
            broadcast=broadcast,
            user_input_queue=session_file_queues[session_id],
        )
        
    except Exception as exc:

        tb = traceback.format_exc()
        log.error("pipeline.operational_failed",
                  session_id=session_id, exc=str(exc))
        await store.mark_failed(session_id, str(exc))
        await broadcast(session_id, _ev(
            step="pipeline_failed", 
            status=AgentStatus.FAILED,
            payload={"note": "Pipeline Failed"},
            error=str(exc),
        ))
        state = await store.get(session_id)
        return state

    # Persist ISO model immediately
    await store.set_iso_model(session_id, iso_model)
    await broadcast(session_id, _ev(
        step="iso_model_ready", status=AgentStatus.RUNNING,
        payload={
            "note": "ISO Model Ready",
        },
    ))

    try:
        research_result = await run_research_agent(
            iso_model=iso_model,
            session_id=session_id,
            broadcast=broadcast,
            domain_context="",
        )
        await store.set_research_result(session_id, research_result)
        ex = research_result.executive_summary

        await broadcast(session_id, _ev(
            step="pipeline_completed", status=AgentStatus.COMPLETED,
            payload={
                "requirements_researched": len(research_result.records),
                "covered": ex.covered if ex else 0,
                "partial": ex.partial if ex else 0,
                "gaps": ex.gaps if ex else 0,
                "technologies_found": ex.technologies_found if ex else 0,
                "standards_cited": ex.standards_cited if ex else 0,
            },
        ))
        
        # ✅ SUCCESS here
        await broadcast(session_id, _ev(
            agent=AgentName.RESEARCH,
            step="research_agent_completed",
            status=AgentStatus.COMPLETED,
            payload={"note": "Research Agent Completed"},
        ))

    except Exception as exc:
        state = await store.get(session_id)  # safe even if None
        # ❌ FAILURE here FIRST
        await broadcast(session_id, _ev(
            agent=AgentName.RESEARCH,
            step="research_agent_failed",
            status=AgentStatus.FAILED,
            payload={"note": "Research Agent Failed"},
            error=str(exc),
        ))
        
        log.error("pipeline.research_failed",
                  session_id=session_id, exc=str(exc))
        #  ISO model saved
        state = await store.get(session_id)
        state.error = f"Research agent failed: {exc}"
        await store.save(state)
        await store.mark_completed(session_id)
        await broadcast(session_id, _ev(
            step="pipeline_completed_research_partial",
            status=AgentStatus.COMPLETED,
            payload={"note": "Pipeline Completed : Research Partial"},
            error=str(exc),
        ))
        
    await broadcast(session_id, _ev(
        agent=AgentName.SUPER,
        step="session_completed",
        status=AgentStatus.COMPLETED,
        payload={"note": "Session Completed"},
    ))

    return await store.get(session_id)
