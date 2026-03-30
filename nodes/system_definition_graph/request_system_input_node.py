from langchain.messages import HumanMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState
from langgraph.types import interrupt, Interrupt


def request_system_input_node(state: SystemDefinitionState, llm):
    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_request_system_input"]

    response = safe_llm_invoke(
        llm,
        [HumanMessage(content=prompt)],
    )

    user_input = interrupt(response.content)

    return {
        "__interrupt__": [
            Interrupt(value={"raw_user_input": user_input})
        ]
    }
