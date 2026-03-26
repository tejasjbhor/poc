from langchain.messages import HumanMessage, SystemMessage
from api.ws_manager_graph import ws_manager_graph

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityState

def validate_process_list_node(state: FacilityState, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_validate_process_list"]

    response = safe_llm_invoke(llm, [
        HumanMessage(content=prompt.format(
            facility_total_surface_area="TODO",
            system_function="TODO",
            process_list_json=state.get("process_list_json")
        ))
    ])

    return {
        "validation_result": response.content
    }