"""Shared LangGraph state types."""

from __future__ import annotations

from typing import Annotated, Any
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    status: str
    phase: str
    turn_count: int
    covered: list[str]
    pending: list[str]
    last_output: str | None


class SACard(TypedDict, total=False):
    title: str
    body: str
    recommended_action: str | None
    suggestion_id: str


class BufferItem(TypedDict, total=False):
    id: str
    for_agent: str
    content: str
    fired: bool
    created_seq: int


class PlatformState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    active_agent: str
    next_agent: str
    session_goal: str
    goal_progress: str
    agents: dict[str, AgentState]
    event_chain: list[dict[str, Any]]
    sa_inferred_domain: str
    sa_inferred_task: str
    sa_phase: str
    sa_thoughts: list[str]
    sa_checklist: list[dict[str, str]]
    sa_card: SACard | None
    sa_readiness_buffer: list[BufferItem]
    sa_context_for_agent: dict[str, str]
    sa_feedback: str | None
