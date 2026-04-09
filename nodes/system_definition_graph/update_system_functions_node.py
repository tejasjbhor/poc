import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from schemas.graphs.system_definition.output import SystemDefinitionOutput
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
                        "current_system_definition": (
                            state.system_definition.model_dump()
                            if state.system_definition
                            else None
                        ),
                    }
                )
            ),
        ],
        response_model=SystemDefinitionOutput,
    )

    return state.model_copy(
        update={
            "system_definition": response,
            # 🔁 go back to interpret
            "graph_name": graph_name,
        }
    )
