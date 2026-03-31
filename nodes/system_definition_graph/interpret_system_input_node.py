import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState
from utils.json_utils import coerce_json


def interpret_system_input_node(state: SystemDefinitionState, llm):
    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_interpret_system_input"]

    raw_input = state.get("first_user_description")

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(content=json.dumps({"first_user_description": raw_input})),
        ],
    )

    raw_llm_interpretation = response.content
    try:
        parsed_llm_interpretation = coerce_json(raw_llm_interpretation)
    except Exception:
        parsed_llm_interpretation = {}

    return {
        "interpreted_input": raw_llm_interpretation,
        "system_functions": parsed_llm_interpretation.get("system_functions", []),
        "assumptions": parsed_llm_interpretation.get("assumptions", []),
        "system_description": parsed_llm_interpretation.get("system_description", ""),
        "step": "REQUEST_FUNCTION_REFINEMENT",
    }
