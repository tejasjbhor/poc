"""Super agent orchestration logic."""

from __future__ import annotations

import traceback
from typing import Callable, Coroutine

import structlog
import asyncio

from state.session_store import session_file_queues
from agents.operational_agent import run_operational_agent
from agents.research_agent import run_research_agent
from schemas.models import AgentEvent, AgentName, AgentStatus, ResearchResult, SessionState



## Need to add dynalic state change , funtion call ..may be no need ( dicuss with ali)

from state.session_store import SessionStore
from utils.user_interaction import request_user_input

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
    state = await store.get(session_id)  # safe even if None
    timeout = 300.0
    
    def _ev(step: str, status: AgentStatus, payload=None, error=None, agent: AgentName = AgentName.SUPER_F1,):
        return AgentEvent(
            session_id=session_id, agent=agent,
            step=step, status=status, payload=payload, error=error,
        ).to_ws()

    # Step 1: signal start
    await broadcast(session_id, _ev(
        agent=AgentName.SUPER_F1,
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
        ranked_candidates = await run_research_agent(
            iso_model=iso_model,
            session_id=session_id,
            user_input_queue=session_file_queues[session_id],
            broadcast=broadcast,
        )
        research_result = {
            "session_id": session_id,
            "records": ranked_candidates,  # list of dicts
        }
        log.info("ranked_candidates", ranked_candidates=ranked_candidates)
        await store.set_research_result(session_id, research_result)

    except Exception as exc:
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
    
    input_data = await request_user_input(
        session_id=session_id,
        agent=AgentName.SUPER_F1,
        user_input_queue=session_file_queues[session_id],
        broadcast=broadcast,
        step="request_user_input",
        data=ranked_candidates,
        label="End Session",
        instructions="End Session.",
        ui_hint={
            "render_as": "validation",
            "actions": ["approve"],
            "primary_action": "approve",
            "approve_label": "End Session",
            "editable": False
        },
        timeout=timeout
    )
    
    # await store.save(state)
    await store.mark_completed(session_id)
        
    await broadcast(session_id, _ev(
        agent=AgentName.SUPER_F1,
        step="session_completed",
        status=AgentStatus.COMPLETED,
        payload={"note": "Session Completed"},
    ))

    return await store.get(session_id)
