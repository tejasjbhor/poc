from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from schemas.layout_schemas import (
    Coordinates,
    LayoutConstraints,
    LayoutNode,
    LayoutRationale,
)
from schemas.system_schemas import SystemFunction
from state.shared_nodes_states.context_definition_node import ExecutionContext


class FacilityLayoutState(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    # =========================
    # User inputs
    # =========================
    raw_user_input: Optional[str] = None
    constraints_user_feedback: Optional[str] = None

    # =========================
    # INPUT GRAPH
    # =========================
    system_description: Optional[str] = None
    system_functions: Optional[List[SystemFunction]] = Field(default_factory=list)
    assumptions: Optional[List[str]] = Field(default_factory=list)

    # =========================
    # CONSTRAINTS
    # =========================
    layout_constraints: Optional[LayoutConstraints] = None

    # =========================
    # OUTPUT LAYOUT GRAPH
    # =========================
    layout: Optional[List[LayoutNode]] = None
    layout_status: Optional[str] = None
    total_area: Optional[float] = None
    facility_coordinates: Optional[Coordinates] = None
    layout_user_feedback: Optional[str] = None
    layout_rationale: Optional[LayoutRationale] = None

    # =========================
    # CONTROL
    # =========================
    execution_context: Optional[ExecutionContext] = None
    step: Optional[str] = None
    graph_name: Optional[str] = None
