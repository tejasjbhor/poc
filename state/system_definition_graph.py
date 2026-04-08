from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.system_schemas import SystemFunction
from state.shared_nodes_states.context_definition_node import ExecutionContext


class SystemDefinitionState(BaseModel):
    model_config = ConfigDict(extra="allow")  # IMPORTANT for LangGraph compatibility

    # LLM → user
    question: Optional[str] = None
    refinement_question: Optional[str] = None

    # User inputs
    first_user_description: Optional[str] = None
    user_refinment_feedback: Optional[str] = None

    # interpreted result
    interpreted_input: Optional[str] = None

    # Graph Outputs
    system_description: Optional[str] = None
    system_functions: Optional[List[SystemFunction]] = Field(default_factory=list)
    assumptions: Optional[List[str]] = Field(default_factory=list)

    # Control flags
    execution_context: Optional[ExecutionContext] = None
    step: Optional[str] = None
    graph_name: Optional[str] = None
