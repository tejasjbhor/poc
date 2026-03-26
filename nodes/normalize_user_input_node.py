import json

from langchain.messages import HumanMessage
from langchain_core.messages import SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityState

def normalize_user_input_node(state: FacilityState, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_normalize_user_input_to_state"]

    response = safe_llm_invoke(llm, [
        SystemMessage(content=prompt),
        HumanMessage(content=json.dumps({
            "raw_user_input": state["raw_user_input"],
            "current_state_json": state["current_state_json"]
        }))
    ])

    return {
        "current_state_json": response.content
    }