from typing import List, TypedDict, Optional, Dict, Any

class SystemFunctionInterface(TypedDict, total=False):
    function_id: str
    materials: List[str]

class SystemFunction(TypedDict, total=False):
    id: str
    name: str
    description: str
    category: str
    surface_area: float
    interfaces_in: List[SystemFunctionInterface]
    interfaces_out: List[SystemFunctionInterface]


class SystemDefinitionState(TypedDict):
    # LLM → user
    question: Optional[str]
    refinement_question: Optional[str]

    # User inputs
    first_user_description: Optional[str]
    raw_user_input: Optional[str]
    user_refinment_feedback: Optional[str]

    # interpreted result
    interpreted_input: Optional[str]

    # Structured state
    current_state_json: Dict[str, Any]

    # Intermediate artifacts
    system_description: Optional[str]
    assumptions: Optional[List[str]]
    system_functions: Optional[List[SystemFunction]]

    # Control flags
    step: str
    validation_result: Optional[str]

    # optional: loop control
    needs_refinement: Optional[bool]

    # Output to user
    message: Optional[str]
