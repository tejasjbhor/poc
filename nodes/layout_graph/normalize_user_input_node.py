import json
import logging

from langchain.messages import HumanMessage
from langchain.messages import SystemMessage
from api.ws_manager_graph import ws_manager_graph

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityState

logger = logging.getLogger(__name__)


def normalize_user_input_node(state: FacilityState, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_normalize_user_input_to_state"]
    logger.warning(f"STATE: {state}")

    raw_input = state.get("raw_user_input") or state.get("value")

    if not raw_input:
        raise ValueError(f"No user input found in state: {state}")

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "raw_user_input": raw_input,
                        "current_state_json": state.get("current_state_json", {}),
                    }
                )
            ),
        ],
    )

    return {"current_state_json": response.content}
