import json

from langchain.messages import HumanMessage, SystemMessage

from api.ws_manager_graph import ws_manager_graph
from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityState

def generate_layout_node(state: FacilityState, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_generate_layout"]

    response = safe_llm_invoke(llm, [
        SystemMessage(content=prompt),
        HumanMessage(content=json.dumps({
            "planning_summary_json": state.get("planning_summary_json")
        }))
    ])

    return {
        "layout_json": response.content
    }