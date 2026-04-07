"""Shared LangGraph state types."""

from __future__ import annotations

from typing import Annotated, Any, List, Optional
from typing_extensions import TypedDict
from langgraph.graph.state import CompiledStateGraph

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from schemas.layout_schemas import (
    Coordinates,
    LayoutConstraints,
    LayoutNode,
    LayoutRationale,
)
from schemas.system_schemas import SystemFunction


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


async def get_state(
    graph: CompiledStateGraph,
    session_id: str,
) -> dict:
    config = {"configurable": {"thread_id": session_id}}
    snapshot = await graph.aget_state(config)
    return dict(snapshot.values) if snapshot else {}


class OverallObserverState(TypedDict, total=False):
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
    # --- System Definition ---
    system_description: Optional[str]
    assumptions: Optional[List[str]]
    system_functions: Optional[List[SystemFunction]]

    # --- Layout ---
    layout_constraints: LayoutConstraints
    layout: List[LayoutNode]
    total_area: float
    facility_coordinates: Coordinates
    layout_user_feedback: Optional[str]
    layout_rationale: LayoutRationale
    layout_status: str

    last_step: str
    step: str
    next_step: str
    graph_name: str
