from typing import Optional, List

from pydantic import BaseModel, ConfigDict


class SystemFunctionInterface(BaseModel):
    model_config = ConfigDict(extra="forbid")

    function_id: Optional[str] = None
    materials: Optional[List[str]] = None


class SystemFunction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    surface_area: Optional[float] = None
    category: Optional[str] = None

    interfaces_in: Optional[List[SystemFunctionInterface]] = None
    interfaces_out: Optional[List[SystemFunctionInterface]] = None
