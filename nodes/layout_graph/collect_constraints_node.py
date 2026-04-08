import json

from helpers.interpret_user_input import is_done_user_input
from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityLayoutState
from langchain.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt


from utils.json_utils import coerce_json


def collect_constraints_node(state: FacilityLayoutState, config, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_collect_layout_constraints"]
    graph_name = getattr(state.execution_context, "current_graph", None)

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "system_description": state.system_description,
                        "system_functions": [
                            f.model_dump() if hasattr(f, "model_dump") else f
                            for f in state.system_functions
                        ],
                        "assumptions": state.assumptions,
                        "layout_constraints": (
                            state.layout_constraints.model_dump()
                            if hasattr(state.layout_constraints, "model_dump")
                            else state.layout_constraints
                        ),
                        "constraints_user_feedback": state.constraints_user_feedback
                        or "",
                    }
                )
            ),
        ],
    )

    try:
        layout_constraints = coerce_json(response.content)
    except Exception:
        layout_constraints = {}

    user_refinment_feedback = interrupt(
        {
            "question": layout_constraints,
            "graph_name": graph_name,
        }
    )

    user_input = user_refinment_feedback.get("raw_user_input", "")

    return state.model_copy(
        update={
            "layout_constraints": layout_constraints,
            "constraints_user_feedback": user_input or "",
            "graph_name": graph_name,
            "step": (
                "GENERATE_LAYOUT"
                if is_done_user_input(user_input)
                else "REFINE_CONSTRAINTS"
            ),
        }
    )
