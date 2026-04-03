from langchain.messages import HumanMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState
from langgraph.types import interrupt


def request_system_input_node(state: SystemDefinitionState, config, llm):
    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_request_system_input"]

    if "question" not in state:
        question = safe_llm_invoke(
            llm,
            [HumanMessage(content=prompt)],
        ).content
    else:
        question = state["question"]

    first_user_description = interrupt(question)

    return {
        "question": question,
        "first_user_description": first_user_description["raw_user_input"],
        "step": "INTERPRET_SYSTEM_INPUT",
    }
