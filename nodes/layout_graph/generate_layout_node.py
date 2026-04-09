from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from schemas.graphs.layout.output import LayoutOutput
from state.facility_layout_graph import FacilityLayoutState


import json
from langchain_core.messages import SystemMessage, HumanMessage


def generate_layout_node(state: FacilityLayoutState, config, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_generate_layout"]
    graph_name = getattr(state.execution_context, "current_graph", None)

    previous_layout = state.final_layout or LayoutOutput()
    layout_constraints = previous_layout.layout_constraints

    payload = {
        "system_definition": (
            state.system_definition.model_dump() if state.system_definition else None
        ),
        "hard_constraints": getattr(layout_constraints, "hard", []),
        "soft_constraints": getattr(layout_constraints, "soft", []),
        "previous_layout": (previous_layout.model_dump() if previous_layout else None),
        "layout_user_feedback": state.layout_user_feedback or "",
    }

    response = safe_llm_invoke(
        llm,
        [SystemMessage(content=prompt), HumanMessage(content=json.dumps(payload))],
        response_model=LayoutOutput,
    )

    return state.model_copy(
        update={
            "final_layout": response.model_copy(
                update={
                    # optional: preserve constraints if model omits them
                    "layout_constraints": layout_constraints
                }
            ),
            "graph_name": graph_name,
            "layout_user_feedback": "",
        }
    )
