from typing import List, Dict, Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.graphs.internet_search.output import InternetSearchOutput
from schemas.domain.context_definition_node import ExecutionContext
from schemas.graphs.layout.input import LayoutInput


class InternetSearchState(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    # --- initial input ---
    question: Optional[str] = None
    raw_user_input: Optional[str] = None

    # --- query phase ---
    user_queries_refinment: Optional[str] = None

    # --- retrieval phase ---
    raw_results: Dict[str, Any] = Field(default_factory=dict)

    # --- extraction phase ---
    candidates: List[Dict[str, Any]] = Field(default_factory=list)

    system_definition: Optional[LayoutInput] = None

    # --- ranking phase ---
    internet_search_outcome: Optional[InternetSearchOutput] = None

    # --- Hydration Request ---
    hydration_issues: Optional[List] = Field(default_factory=list)
    hydration_requester: Optional[str] = None

    # --- control ---
    execution_context: Optional[ExecutionContext] = None
    step: Optional[str] = None
    graph_name: Optional[str] = None
