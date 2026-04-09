from typing import Optional

from pydantic import BaseModel, ConfigDict

from schemas.graphs.system_definition.output import SystemDefinitionOutput
from state.shared_nodes_states.context_definition_node import ExecutionContext


class SystemDefinitionState(BaseModel):
    model_config = ConfigDict(
        extra="allow", arbitrary_types_allowed=True
    )  # IMPORTANT for LangGraph compatibility

    # LLM → user
    question: Optional[str] = None
    refinement_question: Optional[str] = None

    # User inputs
    first_user_description: Optional[str] = None
    user_refinment_feedback: Optional[str] = None

    # interpreted result
    interpreted_input: Optional[str] = None

    # Graph Outputs
    system_definition: Optional[SystemDefinitionOutput] = None

    # Control flags
    execution_context: Optional[ExecutionContext] = None
    step: Optional[str] = None
    graph_name: Optional[str] = None
