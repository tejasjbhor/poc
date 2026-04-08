from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityLayoutState


import json
from langchain_core.messages import SystemMessage, HumanMessage


from utils.json_utils import coerce_json


def generate_layout_node(state: FacilityLayoutState, config, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_generate_layout"]
    graph_name = getattr(state.execution_context, "current_graph", None)
    layout_constraints = state.layout_constraints

    payload = {
        "system_description": state.system_description,
        "system_functions": [f.model_dump() for f in state.system_functions],
        "assumptions": state.assumptions,
        "hard_constraints": layout_constraints.hard if layout_constraints else [],
        "soft_constraints": layout_constraints.soft if layout_constraints else [],
        "layout": [n.model_dump() for n in state.layout] if state.layout else [],
        "layout_user_feedback": state.layout_user_feedback or "",
    }

    response = safe_llm_invoke(
        llm,
        [SystemMessage(content=prompt), HumanMessage(content=json.dumps(payload))],
    )

    raw_output = response.content

    try:
        parsed = coerce_json(raw_output)
    except Exception:
        parsed = {}

    layout_nodes = parsed.get("layout", [])

    return state.model_copy(
        update={
            "layout": layout_nodes,
            "total_area": parsed.get("total_area", 0),
            "layout_status": parsed.get("layout_status", ""),
            "facility_coordinates": parsed.get("facility_coordinates", {}),
            "layout_rationale": parsed.get("layout_rationale", {}),
            "graph_name": graph_name,
            "layout_user_feedback": "",
        }
    )
