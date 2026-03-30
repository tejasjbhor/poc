"""Send text into the super-agent graph (normal chat or answering a paused card)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command


def _session_config(session_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": session_id}}


async def pending_interrupt(
    graph: CompiledStateGraph,
    session_id: str,
) -> Any | None:
    # If the graph is waiting on a card, returns what we showed the user (title, body, etc.). Otherwise None.
    config = _session_config(session_id)
    snap = await graph.aget_state(config)
    pending = tuple(getattr(snap, "interrupts", ()) or ())
    if not pending:
        return None
    return pending[0].value


async def deliver_user_line(
    graph: CompiledStateGraph,
    session_id: str,
    text: str,
) -> None:
    # Old : push one HumanMessage and run the graph.
    # If we are paused on a card, the same string is treated as the answer instead.
    config = _session_config(session_id)
    snap = await graph.aget_state(config)
    pending = tuple(getattr(snap, "interrupts", ()) or ())

    if pending:
        stream_input: Any = Command(resume=text)
    else:
        stream_input = {"messages": [HumanMessage(content=text)]}

    async for _chunk in graph.astream(
        stream_input,
        config=config,
        stream_mode="updates",
    ):
        pass


async def send_message(
    graph: CompiledStateGraph,
    session_id: str,
    text: str,
) -> dict:
    await deliver_user_line(graph, session_id, text)
    return {}


async def apply_feedback(
    graph: CompiledStateGraph,
    session_id: str,
    action: str,
    suggestion_id: str | None,
) -> None:
    # Old way: patch state by hand. If we are paused on a card, answer with the same path as the CLI.
    config = _session_config(session_id)
    snap = await graph.aget_state(config)
    pending = tuple(getattr(snap, "interrupts", ()) or ())
    if pending:
        await deliver_user_line(graph, session_id, action.strip().lower())
        return
    await graph.aupdate_state(
        config,
        {
            "sa_feedback": action,
            "sa_card": None,
        },
    )
