from typing import TypedDict, List, Literal


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


class LayoutConstraints(TypedDict):
    hard: List[str]
    soft: List[str]
