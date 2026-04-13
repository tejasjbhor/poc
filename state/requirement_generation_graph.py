from typing import List, Optional, TypedDict

from schemas.requirement_schemas import GeneratedRequirement
from schemas.system_schemas import SystemFunction


class RequirementGenerationState(TypedDict):
    # From parent (system_definition finished payload)
    system_description: Optional[str]
    system_functions: Optional[List[SystemFunction]]
    assumptions: Optional[List[str]]

    # After REQUEST_FUNCTION_SELECTION
    selected_function_id: Optional[str]

    # Optional cache for interrupt payloads (avoid recomputation on resume replay)
    selection_prompt: Optional[str]
    review_prompt: Optional[str]

    # Last user text from review interrupt (normalized from resume)
    user_requirements_feedback: Optional[str]

    # LLM outputs
    requirements: Optional[List[GeneratedRequirement]]

    # Control (conditional_edges from REQUEST_REQUIREMENTS_REVIEW)
    step: Optional[str]
    graph_name: Optional[str]
