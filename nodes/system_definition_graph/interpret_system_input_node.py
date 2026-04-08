import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState
from utils.json_utils import coerce_json


def interpret_system_input_node(state: SystemDefinitionState, config, llm):
    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_interpret_system_input"]
    graph_name = getattr(state.execution_context, "current_graph", None)

    raw_input = state.first_user_description

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

    return state.model_copy(
        update={
            "interpreted_input": raw_llm_interpretation,
            "system_functions": parsed_llm_interpretation.get("system_functions", []),
            "assumptions": parsed_llm_interpretation.get("assumptions", []),
            "system_description": parsed_llm_interpretation.get(
                "system_description", ""
            ),
            "graph_name": graph_name,
        }
    )
