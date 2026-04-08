import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState
from utils.json_utils import coerce_json


def update_system_functions_node(state: SystemDefinitionState, config, llm):
    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_update_system_functions"]
    graph_name = getattr(state.execution_context, "current_graph", None)

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "user_refinment_feedback": state.user_refinment_feedback,
                        "system_description": state.system_description,
                        "system_functions": [
                            f.model_dump() for f in state.system_functions or []
                        ],
                        "assumptions": state.assumptions,
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

    return state.model_copy(
        update={
            "system_functions": parsed_llm_interpretation.get(
                "system_functions", state.system_functions
            ),
            "assumptions": parsed_llm_interpretation.get(
                "assumptions", state.assumptions
            ),
            "system_description": parsed_llm_interpretation.get(
                "system_description", state.system_description
            ),
            # 🔁 go back to interpret
            "graph_name": graph_name,
        }
    )
