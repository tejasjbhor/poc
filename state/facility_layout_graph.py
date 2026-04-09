from typing import Optional
from pydantic import BaseModel, ConfigDict

from schemas.graphs.layout.input import LayoutInput
from schemas.graphs.layout.output import LayoutOutput
from state.shared_nodes_states.context_definition_node import ExecutionContext


class FacilityLayoutState(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    # =========================
    # User inputs
    # =========================
    raw_user_input: Optional[str] = None
    constraints_user_feedback: Optional[str] = None
    layout_user_feedback: Optional[str] = None

    # =========================
    # INPUT GRAPH
    #
    # =========================
    system_definition: Optional[LayoutInput] = None

    # =========================
    # CONSTRAINTS
    # =========================

    # =========================
    # OUTPUT LAYOUT GRAPH
    # =========================
    final_layout: Optional[LayoutOutput] = None

    # =========================
    # CONTROL
    # =========================
    execution_context: Optional[ExecutionContext] = None
    step: Optional[str] = None
    graph_name: Optional[str] = None
