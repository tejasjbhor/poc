import asyncio
import time

from agents.research_agent import run_research_agent
from schemas.models import (
    AgentEvent,
    AgentName,
    AgentStatus,
    ISO15926Meta,
    ISO15926Model,
)
from state.session_store import session_store


async def main() -> None:
    sid = "smoke-" + str(int(time.time()))
    await session_store.create(sid)

    iso = ISO15926Model(
        meta=ISO15926Meta(standard="ISO-TEST", source_document="dummy"),
        entities=[
            {
                "id": "ent-1",
                "type": "entity",
                "entity_type": "engineering_constraint",
                "name": "REQ-001",
                "statement": "The system shall do X under condition Y.",
                "req_id": "REQ-001",
                "rationale": "Example rationale.",
                "function_id": None,
                "priority": "medium",
                "is_assumption": False,
            }
        ],
        relationships=[],
        properties=[],
    )

    async def broadcast_fn(sid: str, payload: dict) -> None:
        # Mirror the real websocket callback behaviour: parse AgentEvent and store it.
        ev = AgentEvent.model_validate(payload)
        await session_store.append_event(sid, ev)

    task = asyncio.create_task(
        run_research_agent(
            iso_model=iso,
            session_id=sid,
            broadcast=broadcast_fn,
            domain_context="",
        )
    )

    confirmed = False
    deadline = time.monotonic() + 60
    needs = False
    while time.monotonic() < deadline:
        st = await session_store.get(sid)
        if st:
            needs = any(
                (e.agent == AgentName.RESEARCH and e.step == "step2_needs_confirmation")
                for e in st.events
            )
            if needs and not confirmed:
                ev = AgentEvent(
                    session_id=sid,
                    agent=AgentName.RESEARCH,
                    step="step2_confirmed",
                    status=AgentStatus.COMPLETED,
                    payload={"confirmed": True},
                )
                await session_store.append_event(sid, ev)
                confirmed = True
                break
        await asyncio.sleep(1)

    res = await asyncio.wait_for(task, timeout=120)
    st2 = await session_store.get(sid)
    needs2 = any(
        (e.agent == AgentName.RESEARCH and e.step == "step2_needs_confirmation")
        for e in (st2.events if st2 else [])
    )
    confirmed2 = any(
        (e.agent == AgentName.RESEARCH and e.step == "step2_confirmed")
        for e in (st2.events if st2 else [])
    )

    print("SMOKE_OK", needs2, confirmed2, "records=", len(res.records))


if __name__ == "__main__":
    asyncio.run(main())

