import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityState


def prepare_summary_node(state: FacilityState, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_prepare_layout_summary"]

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "facility_total_surface_area": "TODO",
                        "system_function": "TODO",
                        "process_list_json": state.get("process_list_json"),
                        "layout_constraints_json": state.get("layout_constraints_json"),
                    }
                )
            ),
        ],
    )

    return {"planning_summary_json": response.content}
