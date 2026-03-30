import json
import logging

from langchain.messages import HumanMessage
from langchain.messages import SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState

logger = logging.getLogger(__name__)


def normalize_system_input_node(state: SystemDefinitionState, llm):
    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_normalize_user_input_to_state"]
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
