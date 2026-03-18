"""Super agent orchestration logic."""

from __future__ import annotations

import json
from pathlib import Path
import traceback
from typing import Callable, Coroutine

import structlog

from agents.operational_agent import run_operational_agent
from agents.research_agent import run_research_agent
from schemas.models import (
    AgentEvent,
    AgentName,
    AgentStatus,
    ISO15926Meta,
    ISO15926Model,
    SessionState,
)

## Need to add dynalic state change , funtion call ..may be no need ( dicuss with ali)

from state.session_store import SessionStore

log = structlog.get_logger(__name__)

BroadcastFn = Callable[[str, dict], Coroutine]


def _build_iso_model_from_snapshot(snapshot_path: Path) -> ISO15926Model:
    """
    Convert the notebook snapshot JSON (iso15926_model with possible_individuals/classes/things)
    into our API's ISO15926Model shape (meta/entities/relationships/properties).

    We map snapshot "researchable" items into `engineering_constraint` entities so that
    `ISO15926Model.get_requirements()` returns non-zero and the Research Agent can run.
    """
    raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    model_data = raw.get("iso15926_model", raw)
    meta_in = (model_data or {}).get("meta", {}) or {}

    meta = ISO15926Meta(
        exported_at=str(meta_in.get("exported_at") or ISO15926Meta().exported_at),
        version=str(meta_in.get("version") or "snapshot"),
        standard=str(meta_in.get("standard") or "ISO/TS 15926-2:2003"),
        source_document=snapshot_path.name,
        generated_by="snapshot_loader",
    )

    # Classes to treat as researchable inputs (per working notebook Agent 2)
    researchable_classes = {
        "stakeholder_need",
        "regulatory_clause",
        "engineering_constraint",
        "operational",
        "lifecycle",
        "failure",
        "maintenance",
        "degraded",
    }

    req_type_map = {
        "stakeholder_need": "functional",
        "regulatory_clause": "regulatory",
        "engineering_constraint": "functional",
        "operational": "operational",
        "lifecycle": "operational",
        "failure": "safety",
        "maintenance": "maintenance",
        "degraded": "performance",
    }

    all_ents = []
    for section in ("possible_individuals", "classes", "things", "entities"):
        all_ents.extend((model_data or {}).get(section, []) or [])

    entities = []
    counter = 1
    for e in all_ents:
        cls = e.get("class") or e.get("entity_type") or ""
        if cls not in researchable_classes:
            continue

        req_id = e.get("req_id") or f"REQ-{counter:03d}"
        counter += 1

        name = e.get("name") or req_id
        statement = (
            e.get("statement")
            or e.get("description")
            or e.get("excerpt")
            or e.get("applicability")
            or name
        )

        entities.append(
            {
                "id": e.get("id") or e.get("uuid") or "",  # optional
                "type": "entity",
                "entity_type": "engineering_constraint",
                "name": str(name)[:200],
                "description": (e.get("description") or "")[:800] if isinstance(e.get("description"), str) else None,
                "statement": str(statement)[:2000],
                "rationale": (e.get("rationale") or e.get("description") or "")[:800],
                "req_id": req_id,
                "requirement_type": req_type_map.get(cls, "functional"),
                "priority": e.get("priority"),
                "function_id": e.get("function_id"),
                "is_assumption": bool(e.get("is_assumption", False)),
            }
        )

    return ISO15926Model(
        meta=meta,
        entities=entities,
        relationships=[],
        properties=[],
    )


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

    # Step 2: run operational agent
    try:
        iso_model = await run_operational_agent(
            session_id=session_id,
            broadcast=broadcast,
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
            "entities": len(iso_model.entities),
            "requirements": len(iso_model.get_requirements()),
            "relationships": len(iso_model.relationships),
        },
    ))
    

    req_count = len(iso_model.get_requirements())
    if req_count == 0:
        # OLD behavior (kept for reference; do not delete):
        # await store.mark_completed(session_id)
        # await broadcast(session_id, _ev(
        #     step="no_requirements_pipeline_completed",
        #     status=AgentStatus.COMPLETED,
        #     payload={"note": "Pipeline Completed : No Requirements"},
        # ))
        # await broadcast(session_id, _ev(
        #     agent=AgentName.SUPER,
        #     step="session_completed",
        #     status=AgentStatus.COMPLETED,
        #     payload={"note": "Session Completed"},
        # ))
        # return await store.get(session_id)

        # NEW behavior: load local snapshot and convert it into engineering_constraint entities
        try:
            snapshot_path = Path("data") / "engineering_model_iso15926.json"
            iso_model = _build_iso_model_from_snapshot(snapshot_path)

            await store.set_iso_model(session_id, iso_model)
            await broadcast(session_id, _ev(
                step="iso_model_fallback_loaded",
                status=AgentStatus.RUNNING,
                payload={
                    "note": "Loaded fallback ISO model snapshot",
                    "source": str(snapshot_path),
                    "entities": len(iso_model.entities),
                    "requirements": len(iso_model.get_requirements()),
                },
            ))

        except Exception as exc:
            log.error("pipeline.snapshot_load_failed", session_id=session_id, exc=str(exc))
            await store.mark_completed(session_id)
            await broadcast(session_id, _ev(
                step="no_requirements_pipeline_completed",
                status=AgentStatus.COMPLETED,
                payload={"note": "Pipeline Completed : No Requirements (snapshot load failed)"},
                error=str(exc),
            ))
            await broadcast(session_id, _ev(
                agent=AgentName.SUPER,
                step="session_completed",
                status=AgentStatus.COMPLETED,
                payload={"note": "Session Completed"},
            ))
            return await store.get(session_id)

    await broadcast(session_id, _ev(
        agent=AgentName.RESEARCH,
        step="research_agent_started",
        status=AgentStatus.RUNNING,
        payload={"note": "Research Agent Started"},
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
