from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class InternetSearchOutput(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    ranked_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    system_understanding: Dict[str, Any] = Field(default_factory=dict)
    queries: List[str] = Field(default_factory=list)
