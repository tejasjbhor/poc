from typing import List, TypedDict, Optional, Dict, Any


class SystemFunction(TypedDict, total=False):
    name: str
    description: str
    category: str
    inputs: List[str]
    outputs: List[str]
    surface_area: float
    interfaces_in: List[str]
    interfaces_out: List[str]


class SystemDefinitionState(TypedDict):
    # Raw user input
    raw_user_input: Optional[str]

    # Structured state
    current_state_json: Dict[str, Any]

    # Intermediate artifacts
    system_description: Optional[str]
    system_functions: Optional[List[SystemFunction]]

    # Control flags
    last_step: Optional[str]
    validation_result: Optional[str]

    # Output to user
    message: Optional[str]
