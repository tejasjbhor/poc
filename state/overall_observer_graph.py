"""Shared LangGraph state types."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


from schemas.domain.layout import (
    Coordinates,
    LayoutConstraints,
    LayoutNode,
    LayoutRationale,
)
from schemas.domain.system import SystemFunction
from state.shared_nodes_states.context_definition_node import ExecutionContext

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any


class OverallObserverState(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    # --- System Definition ---
    system_description: Optional[str] = None
    system_functions: Optional[List[SystemFunction]] = Field(default_factory=list)
    assumptions: Optional[List[str]] = Field(default_factory=list)

    # =========================
    # LAYOUT GRAPH
    # =========================
    layout: Optional[List[LayoutNode]] = None
    layout_status: Optional[str] = None
    total_area: Optional[float] = None
    facility_coordinates: Optional[Coordinates] = None
    layout_user_feedback: Optional[str] = None
    layout_rationale: Optional[LayoutRationale] = None
    layout_constraints: Optional[LayoutConstraints] = None
    layout_status: Optional[str] = None

    # --- Internet Search ---
    system_understanding: Dict[str, Any] = Field(default_factory=dict)
    queries: List[str] = Field(default_factory=list)
    ranked_candidates: List[Dict[str, Any]] = Field(default_factory=list)

    # --- Execution Context ---
    execution_context: Optional[ExecutionContext] = None

    # --- Graph Control ---
    last_step: Optional[str] = None
    step: Optional[str] = None
    next_step: Optional[str] = None
    graph_name: Optional[str] = None
