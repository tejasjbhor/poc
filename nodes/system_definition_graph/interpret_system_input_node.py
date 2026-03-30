import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState


def interpret_system_input_node(state: SystemDefinitionState, llm):
    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_interpret_system_input"]

    raw_input = state.get("raw_user_input") or state.get("value")

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(content=json.dumps({"raw_user_input": raw_input})),
        ],
    )

    return {
        "system_functions_json": response.content,
        "last_step": "INTERPRET_SYSTEM_INPUT",
    }
