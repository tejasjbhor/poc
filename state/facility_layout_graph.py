from typing import Optional, TypedDict, List, Literal, Dict, Tuple


class Interface(TypedDict):
    function_id: str
    materials: List[str]


class SystemFunction(TypedDict):
    id: str
    name: str
    description: str
    surface_area: float

    interfaces_in: List[Interface]
    interfaces_out: List[Interface]


class Coordinates(TypedDict):
    x: float
    y: float
    width: float
    height: float


class LayoutConnection(TypedDict):
    connected_component_id: str
    direction: Literal["up", "down", "left", "right", "bidirectional"]
    shared_materials: List[str]
    connection_weight: float


class LayoutNode(TypedDict):
    id: str
    function_name: str
    surface_area: float

    coordinates: Coordinates
    connections: List[LayoutConnection]


class LayoutRationale(TypedDict):
    organizing_principle: str
    major_adjacency_choices: List[str]
    assumptions: List[str]
    constraint_tradeoffs: List[str]


class Constraints(TypedDict):
    hard: List[str]
    soft: List[str]


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
    constraints: Constraints

    # =========================
    # INTERMEDIATE (optional but useful)
    # =========================
    flow_edges: List[dict]  # derived from interfaces
    ordered_flow: List[str]
    zones: List[dict]

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
