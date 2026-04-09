from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class SystemFunctionInterface(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    function_id: Optional[str] = None
    materials: Optional[List[str]] = None


class SystemFunction(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    id: Optional[str] = Field(default=None, description="Identifier of the function, must be unique.")
    name: Optional[str] = None
    description: Optional[str] = None
    surface_area: Optional[float] = Field(default=0, description="Area in m². Must be numeric.")
    category: Optional[str] = None

    interfaces_in: Optional[List[SystemFunctionInterface]] = None
    interfaces_out: Optional[List[SystemFunctionInterface]] = None
