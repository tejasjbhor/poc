from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.domain.system import SystemFunction


class SystemDefinitionOutput(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    system_description: Optional[str] = None
    system_functions: Optional[List[SystemFunction]] = Field(default_factory=list)
    assumptions: Optional[List[str]] = Field(default_factory=list)
