import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState


def validate_system_functions_node(state: SystemDefinitionState, llm):
    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_validate_system_functions"]

    system_functions = state.get("system_functions_json")

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps({"system_functions_json": system_functions})
            ),
        ],
    )

    content = response.content.strip()

    if content == "SYSTEM_FUNCTIONS_ACCEPTED":
        return {
            "validation_status": {"accepted": True},
            "last_step": "VALIDATE_SYSTEM_FUNCTIONS",
        }

    return {
        "validation_status": {"accepted": False},
        "messages": [response],
        "last_step": "VALIDATE_SYSTEM_FUNCTIONS",
    }
