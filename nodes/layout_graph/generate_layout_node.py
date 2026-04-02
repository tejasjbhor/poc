from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityLayoutState
from langchain.messages import HumanMessage


import json
from langchain_core.messages import SystemMessage, HumanMessage


import json
from langchain_core.messages import SystemMessage, HumanMessage

from utils.json_utils import coerce_json


def generate_layout_node(state: FacilityLayoutState, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_generate_layout"]

    payload = {
        "system_description": state.get("system_description"),
        "system_functions": state.get("system_functions"),
        "assumptions": state.get("assumptions", []),
        "hard_constraints": state.get("constraints", {}).get("hard", []),
        "soft_constraints": state.get("constraints", {}).get("soft", []),
        "layout": state.get("layout", None),
        "layout_user_feedback": state.get("layout_user_feedback", ""),
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

    # -------------------------
    # State update (single source of truth)
    # -------------------------
    return {
        "layout": parsed.get("layout", []),
        "total_area": parsed.get("total_area", 0),
        "layout_status": parsed.get("layout_status", ""),
        "facility_coordinates": parsed.get("facility_coordinates", {}),
        "layout_rationale": parsed.get("layout_rationale", {}),
        "layout_user_feedback": "",  # clear feedback after applying it
        "step": "REVIEW_LAYOUT",
    }
