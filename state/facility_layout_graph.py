from typing import Optional, TypedDict, List

from schemas.layout_schemas import (
    Coordinates,
    LayoutConstraints,
    LayoutNode,
    LayoutRationale,
)
from schemas.system_schemas import SystemFunction


class FacilityLayoutState(TypedDict):
    # User inputs
    raw_user_input: Optional[str]
    constraints_user_feedback: Optional[str]

    # =========================
    # INPUT GRAPH
    # =========================
    system_description: str
    system_functions: List[SystemFunction]
    assumptions: List[str]

    # =========================
    # CONSTRAINTS (SIMPLIFIED)
    # =========================
    layout_constraints: LayoutConstraints

    # =========================
    # OUTPUT LAYOUT GRAPH
    # =========================
    layout: List[LayoutNode]
    layout_status: str
    total_area: float
    facility_coordinates: Coordinates
    layout_user_feedback: Optional[str]
    layout_rationale: LayoutRationale

    # COptional[ontrol flags]
    step: Optional[str]
    graph_name: str
