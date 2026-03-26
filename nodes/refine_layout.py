from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityState


def refine_layout_node(state: FacilityState, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_refine_layout"]

    response = safe_llm_invoke(llm, [
        HumanMessage(content=prompt.format(
            previous_layout_json=state["layout_json"],
            planning_summary_json=state["planning_summary_json"],
            user_feedback=state["raw_user_input"]
        ))
    ])

    return {
        "layout_json": response.content
    }