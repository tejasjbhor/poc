import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState


def update_system_functions_node(state: SystemDefinitionState, llm):
    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_update_system_functions"]

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "current_system_functions": state.get("system_functions_json"),
                        "user_feedback": state.get("raw_user_input")
                        or state.get("value"),
                    }
                )
            ),
        ],
    )

    return {
        "system_functions_json": response.content,
        "last_step": "UPDATE_SYSTEM_FUNCTIONS",
    }