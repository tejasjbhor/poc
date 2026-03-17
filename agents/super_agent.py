"""Super agent orchestration logic."""

from __future__ import annotations

import traceback
from typing import Callable, Coroutine

import structlog

from agents.operational_agent import run_operational_agent
from agents.research_agent import run_research_agent
from schemas.models import AgentEvent, AgentName, AgentStatus, SessionState

## Need to add dynalic state change , funtion call ..may be no need ( dicuss with ali)

from state.session_store import SessionStore

log = structlog.get_logger(__name__)

BroadcastFn = Callable[[str, dict], Coroutine]


async def run_pipeline(
    session_id: str,
    pdf_bytes: bytes,
    filename: str,
    broadcast: BroadcastFn,
    store: SessionStore,
    domain_context: str = "",
    skip_research: bool = False,
) -> SessionState:
    """
    Full orchestration pipeline.
    Returns the final SessionState regardless of success/failure.
    Never raises — all errors are caught, persisted, and broadcast.
    """

    def _ev(step: str, status: AgentStatus, payload=None, error=None):
        return AgentEvent(
            session_id=session_id, agent=AgentName.SUPER,
            step=step, status=status, payload=payload, error=error,
        ).to_ws()

    # Step 1: signal start
    await broadcast(session_id, _ev(
        step="pipeline_started", status=AgentStatus.RUNNING,
        payload={"filename": filename, "skip_research": skip_research},
    ))

    # Step 2: run operational agent
    await broadcast(session_id, _ev(
        step="dispatching_operational_agent", status=AgentStatus.RUNNING,
    ))

    try:
        iso_model = await run_operational_agent(
            pdf_bytes=pdf_bytes,
            filename=filename,
            session_id=session_id,
            broadcast=broadcast,
            domain_context=domain_context,
        )
    except Exception as exc:
        tb = traceback.format_exc()
        log.error("pipeline.operational_failed",
                  session_id=session_id, exc=str(exc))
        await store.mark_failed(session_id, str(exc))
        await broadcast(session_id, _ev(
            step="pipeline_failed", status=AgentStatus.FAILED,
            error=str(exc),
        ))
        state = await store.get(session_id)
        return state

    # Persist ISO model immediately
    await store.set_iso_model(session_id, iso_model)
    await broadcast(session_id, _ev(
        step="iso_model_ready", status=AgentStatus.RUNNING,
        payload={
            "entities": len(iso_model.entities),
            "requirements": len(iso_model.get_requirements()),
            "relationships": len(iso_model.relationships),
        },
    ))

    # Step 3: run research agent
    if skip_research:
        await store.mark_completed(session_id)
        await broadcast(session_id, _ev(
            step="pipeline_completed_no_research",
            status=AgentStatus.COMPLETED,
        ))
        return await store.get(session_id)

    req_count = len(iso_model.get_requirements())
    if req_count == 0:
        await store.mark_completed(session_id)
        await broadcast(session_id, _ev(
            step="no_requirements_pipeline_completed",
            status=AgentStatus.COMPLETED,
        ))
        return await store.get(session_id)

    await broadcast(session_id, _ev(
        step="dispatching_research_agent", status=AgentStatus.RUNNING,
        payload={"requirements_to_research": req_count},
    ))

    try:
        research_result = await run_research_agent(
            iso_model=iso_model,
            session_id=session_id,
            broadcast=broadcast,
            domain_context=domain_context,
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

    except Exception as exc:
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
            error=str(exc),
        ))

    return await store.get(session_id)
