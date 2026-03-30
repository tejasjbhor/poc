from typing import TypedDict, Optional, Dict, Any


class FacilityState(TypedDict):
    # Raw user input
    raw_user_input: Optional[str]

    # Structured state
    current_state_json: Dict[str, Any]

    # Intermediate artifacts
    process_list_json: Optional[str]
    layout_constraints_json: Optional[str]
    planning_summary_json: Optional[str]
    layout_json: Optional[str]

    # Control flags
    last_step: Optional[str]
    validation_result: Optional[str]

    # Output to user
    message: Optional[str]
