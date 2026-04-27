from langchain.messages import HumanMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState
from langgraph.types import interrupt


def request_system_input_node(state: SystemDefinitionState, config, llm):
    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_request_system_input"]
    graph_name = getattr(state.execution_context, "current_graph", None)
    system_definition = state.system_definition

    if system_definition:
        return state.model_copy(
            update={
                "step": "REQUEST_FUNCTION_REFINEMENT",
                "graph_name": graph_name,
            }
        )
    else:
        if state.question is None:
            question = safe_llm_invoke(
                llm,
                [HumanMessage(content=prompt)],
            ).content
        else:
            question = state.question

        first_user_description = interrupt(
            {"question": question, "graph_name": graph_name}
        )

        return state.model_copy(
            update={
                "question": question,
                "first_user_description": first_user_description["raw_user_input"],
                "graph_name": graph_name,
                "step": "INTERPRET_SYSTEM_INPUT",
            }
        )
