from langchain.messages import HumanMessage, SystemMessage
from langgraph.types import Interrupt, interrupt

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityState

def request_feedback_node(state: FacilityState, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_request_layout_feedback"]

    response = safe_llm_invoke(llm, [HumanMessage(content=prompt)])

    user_input = interrupt(response.content)

    return {"__interrupt__": [Interrupt(value={
        "raw_user_input": user_input
    })]}