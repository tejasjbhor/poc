"""LangGraph: user_input -> sa_router -> agent -> sa_observer -> END."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent_registry import (
    get_all_agent_ids,

        get_default_active_agent_id,

      get_default_agent_states,
    get_node_fn,
)
from state import PlatformState
from super_agent import sa_observer_node

logger = logging.getLogger(__name__)


def _merge_agents(existing: dict, update: dict) -> dict:
    merged = dict(existing or {})
    for agent_id, agent_state in (update or {}).items():
        if agent_id in merged:
            merged[agent_id] = {**merged[agent_id], **agent_state}
        else:
            merged[agent_id] = agent_state
    return merged


def _append_events(existing: list, update: list) -> list:
    return list(existing or []) + list(update or [])


def _merge_sa_context(existing: dict, update: dict) -> dict:
    merged = dict(existing or {})
    for agent_id, ctx in (update or {}).items():
        merged[agent_id] = ctx
    return merged


class GraphState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    active_agent: str
    next_agent: str
    session_goal: str
    goal_progress: str
    agents: Annotated[dict, _merge_agents]
    event_chain: Annotated[list, _append_events]
    sa_inferred_domain: str
    sa_inferred_task: str
    sa_phase: str
    sa_thoughts: list
    sa_checklist: list
    sa_card: Any
    sa_readiness_buffer: list
    sa_context_for_agent: Annotated[dict, _merge_sa_context]
    sa_feedback: Any


async def user_input_node(state: PlatformState) -> dict:
    import time

    messages = state.get("messages") or []
    last_human = next(
        (m for m in reversed(messages) if getattr(m, "type", "") == "human"),
        None,
    )

    new_event = {}
    if last_human:
        new_event = {
            "seq":     len(state.get("event_chain") or []) + 1,
            "agent":   "user",
            "type":    "input",
            "content": getattr(last_human, "content", ""),
            "ts":      time.time(),
        }

    agents = dict(state.get("agents") or {})
    if not agents:
        agents = get_default_agent_states()

    return {
        "agents":      agents,
        "event_chain": [new_event] if new_event else [],
    }


async def sa_router_node(state: PlatformState) -> dict:
    all_ids = set(get_all_agent_ids())
    default = get_default_active_agent_id()

    na = (state.get("next_agent") or "").strip()
    if na in all_ids:
        chosen = na
    else:
        cur = (state.get("active_agent") or "").strip()
        chosen = cur if cur in all_ids else default

    logger.info("sa_router: active_agent=%s", chosen)
    return {"active_agent": chosen}


def build_graph(checkpointer: Any | None = None) -> CompiledStateGraph:
    if checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()

    builder = StateGraph(GraphState)

    builder.add_node("user_input", user_input_node)
    builder.add_node("sa_router", sa_router_node)
    builder.add_node("sa_observer", sa_observer_node)

    all_agent_ids = get_all_agent_ids()
    for agent_id in all_agent_ids:
        node_fn = get_node_fn(agent_id)
        builder.add_node(agent_id, node_fn)
        logger.info("Graph: registered node '%s'", agent_id)

    builder.add_edge(START, "user_input")
    builder.add_edge("user_input", "sa_router")

    def _pick_agent(state: GraphState) -> str:
        aid = state.get("active_agent") or ""
        if aid in all_agent_ids:
            return aid
        d = get_default_active_agent_id()
        if d in all_agent_ids:
            return d
        return all_agent_ids[0] if all_agent_ids else ""

    path_map = {aid: aid for aid in all_agent_ids}
    builder.add_conditional_edges("sa_router", _pick_agent, path_map)

    for agent_id in all_agent_ids:
        builder.add_edge(agent_id, "sa_observer")
    builder.add_edge("sa_observer", END)

    graph = builder.compile(checkpointer=checkpointer)
    logger.info("Graph compiled. Checkpointer: %s", type(checkpointer).__name__)
    return graph


async def send_message(
    graph:      CompiledStateGraph,
    session_id: str,
    text:       str,
) -> dict:
    config = {"configurable": {"thread_id": session_id}}
    input_state = {"messages": [HumanMessage(content=text)]}

    final_state: dict = {}
    async for chunk in graph.astream(
        input_state,
        config=config,
        stream_mode="updates",
    ):
        for node_name, updates in chunk.items():
            logger.debug("Graph stream: node=%s keys=%s", node_name, list(updates.keys()))
        final_state.update(chunk)

    return final_state


async def get_state(
    graph:      CompiledStateGraph,
    session_id: str,
) -> dict:
    config = {"configurable": {"thread_id": session_id}}
    snapshot = await graph.aget_state(config)
    return dict(snapshot.values) if snapshot else {}


async def apply_feedback(
    graph:      CompiledStateGraph,
    session_id: str,
    action:     str,
    suggestion_id: str | None,
) -> None:
    config = {"configurable": {"thread_id": session_id}}
    await graph.aupdate_state(
        config,
        {
            "sa_feedback": action,
            "sa_card":     None,
        },
    )
    logger.info("SA feedback applied: session=%s action=%s", session_id, action)
