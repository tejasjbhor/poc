import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from schemas.graphs.system_definition.output import SystemDefinitionOutput
from state.system_definition_graph import SystemDefinitionState


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
        response_model=SystemDefinitionOutput,
    )

    return state.model_copy(
        update={
            "interpreted_input": response.model_dump_json(),
            "system_definition": response,
            "graph_name": graph_name,
        }
    )
