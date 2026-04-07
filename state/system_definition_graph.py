from typing import List, TypedDict, Optional

from schemas.system_schemas import SystemFunction
from state.shared_nodes_states.context_definition_node import ExecutionContext


class SystemDefinitionState(TypedDict):
    # LLM → user
    question: Optional[str]
    refinement_question: Optional[str]

    # User inputs
    first_user_description: Optional[str]
    user_refinment_feedback: Optional[str]

    # interpreted result
    interpreted_input: Optional[str]

    # Graph Outputs
    system_description: Optional[str]
    assumptions: Optional[List[str]]
    system_functions: Optional[List[SystemFunction]]

    # Control flags
    execution_context: ExecutionContext
    step: Optional[str]
    graph_name: Optional[str]
