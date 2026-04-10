from typing import Annotated, Optional, List, Literal

from pydantic import BaseModel, ConfigDict, Field


class Coordinates(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    x: float
    y: float
    width: float
    height: float


class LayoutConnection(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    connected_component_id: str
    direction: Annotated[
        Literal["up", "down", "left", "right", "bidirectional"] | None,
        Field(description="Direction of the connection between the two functions."),
    ] = None
    shared_materials: Optional[List[str]] = None
    connection_weight: Optional[float] = None


class LayoutNode(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    id: str
    function_name: str
    surface_area: float

    coordinates: Coordinates
    connections: Optional[List[LayoutConnection]] = None


class LayoutRationale(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    organizing_principle: Optional[str] = None
    major_adjacency_choices: Optional[List[str]] = None
    assumptions: Optional[List[str]] = None
    constraint_tradeoffs: Optional[List[str]] = None


class LayoutConstraints(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    hard: Optional[List[str]] = None
    soft: Optional[List[str]] = None
