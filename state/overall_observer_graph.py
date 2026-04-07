"""Shared LangGraph state types."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


from schemas.layout_schemas import (
    Coordinates,
    LayoutConstraints,
    LayoutNode,
    LayoutRationale,
)
from schemas.system_schemas import SystemFunction
from state.shared_nodes_states.context_definition_node import ExecutionContext


class OverallObserverState(TypedDict, total=False):
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

    # --- Internet Search ---
    system_understanding: Dict[str, Any]
    queries: List[str]
    ranked_candidates: List[Dict[str, Any]]

    execution_context: ExecutionContext
    last_step: str
    step: str
    next_step: str
    graph_name: str
