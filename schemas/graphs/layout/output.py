from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.domain.layout import (
    Coordinates,
    LayoutConstraints,
    LayoutNode,
    LayoutRationale,
)


class LayoutOutput(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    layout: Optional[List[LayoutNode]] = None
    layout_status: Optional[str] = None
    total_area: Optional[float] = Field(default=0, description="Area in m². Must be numeric.")
    facility_coordinates: Optional[Coordinates] = None
    layout_rationale: Optional[LayoutRationale] = None
    layout_constraints: Optional[LayoutConstraints] = None
