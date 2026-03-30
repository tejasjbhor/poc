import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState

from langgraph.types import interrupt, Interrupt


def request_refinement_node(state: SystemDefinitionState, llm):
    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_request_function_refinement"]

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "system_functions_json": state.get("system_functions_json"),
                        "assumptions": state.get("assumptions", []),
                    }
                )
            ),
        ],
    )

    user_input = interrupt(response.content)

    return {"__interrupt__": [Interrupt(value={"raw_user_input": user_input})]}
