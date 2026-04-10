"""Shared LangGraph state types."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


from schemas.graphs.internet_search.output import InternetSearchOutput
from schemas.graphs.layout.output import LayoutOutput
from schemas.graphs.system_definition.output import SystemDefinitionOutput
from schemas.domain.context_definition_node import ExecutionContext

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any


class OverallObserverState(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    # --- System Definition ---
    system_definition: Optional[SystemDefinitionOutput] = None

    # =========================
    # LAYOUT GRAPH
    # =========================
    final_layout: Optional[LayoutOutput] = None

    # =========================
    # INTERNET SEARCH GRAPH
    # =========================
    internet_search_outcome: Optional[InternetSearchOutput] = None

    # --- Execution Context ---
    execution_context: Optional[ExecutionContext] = None

    # --- Hydration Request ---
    hydration_issues: Optional[List] = Field(default_factory=list)
    hydration_requester: Optional[str] = None
    reasoning: Optional[str] = None

    # --- Graph Control ---
    last_step: Optional[str] = None
    step: Optional[str] = None
    next_step: Optional[str] = None
    graph_name: Optional[str] = None
