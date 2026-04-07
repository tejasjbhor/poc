from typing import List, TypedDict, Optional

from schemas.system_schemas import SystemFunction


class SystemDefinitionState(TypedDict):
    # LLM → user
    question: Optional[str]
    refinement_question: Optional[str]

    # User inputs
    first_user_description: Optional[str]
    user_refinment_feedback: Optional[str]

    # interpreted result
    interpreted_input: Optional[str]

    # Intermediate artifacts
    system_description: Optional[str]
    assumptions: Optional[List[str]]
    system_functions: Optional[List[SystemFunction]]

    # Control flags
    step: Optional[str]
    graph_name: Optional[str]
    validation_result: Optional[str]

    # optional: loop control
    needs_refinement: Optional[bool]
