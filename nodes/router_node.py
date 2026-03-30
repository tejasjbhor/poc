from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Interrupt
from api.ws_manager_graph import ws_manager_graph

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityState


def route_from_step(state: FacilityState):
    """
    Simple safe getter for last_step in state.
    Returns default starting step if missing.
    """

    print(f"➡️ TRANSITION: {state.get('last_step')} → ASK_OVERALL_SURFACE_AND_FUNCTION")

    return state.get("last_step") or "ASK_OVERALL_SURFACE_AND_FUNCTION"


def router_node(state: FacilityState, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_detect_next_workflow_step"]

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Current state: {state}"),
        ],
    )

    # Get LLM output text safely
    full_text = getattr(response, "text", None) or response[0].content

    # Extract the last line as token
    next_step = full_text.strip().splitlines()[-1].strip()

    # Fallback if LLM returns nothing
    if not next_step:
        next_step = route_from_step(state)

    # If this step requires user input, wrap in Interrupt
    if next_step.startswith("ASK_"):
        return {"__interrupt__": [Interrupt(value=next_step)]}

    print(f"➡️ TRANSITION: {state.get('last_step')} → {next_step}")

    # Otherwise, just update last_step in state
    return {"last_step": next_step}
