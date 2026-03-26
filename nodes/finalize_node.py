
from langchain.messages import HumanMessage, SystemMessage

from api.ws_manager_graph import ws_manager_graph
from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityState


def finalize_node(state: FacilityState, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_finalize_approved_layout"]
    
    response = safe_llm_invoke(llm, [
        HumanMessage(content=prompt.format(
            approved_layout_json=state.get("layout_json")
        ))
    ])

    return {
        "message": response.content
    }