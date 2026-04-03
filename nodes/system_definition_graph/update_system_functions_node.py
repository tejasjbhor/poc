import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState
from utils.json_utils import coerce_json


def update_system_functions_node(state: SystemDefinitionState, config, llm):
    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_update_system_functions"]

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "user_feedback": state.get("user_refinment_feedback"),
                        "system_description": state.get("system_description"),
                        "system_functions": state.get("system_functions"),
                        "assumptions": state.get("assumptions"),
                    }
                )
            ),
        ],
    )

    raw_llm_interpretation = response.content

    try:
        parsed_llm_interpretation = coerce_json(raw_llm_interpretation)
    except Exception:
        parsed_llm_interpretation = {}

    return {
        "system_functions": parsed_llm_interpretation.get(
            "system_functions", state.get("system_functions")
        ),
        "assumptions": parsed_llm_interpretation.get(
            "assumptions", state.get("assumptions")
        ),
        "system_description": parsed_llm_interpretation.get(
            "system_description", state.get("system_description")
        ),
        # 🔁 go back to interpret
        "step": "INTERPRET_SYSTEM_INPUT",
    }
