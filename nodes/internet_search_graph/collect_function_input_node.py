import json

from langgraph.types import interrupt
from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS


def collect_function_input_node(state: InternetSearchState, config, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_collect_function_input"]
    graph_name = getattr(state.execution_context, "current_graph", None)

    if not state.question:
        question = safe_llm_invoke(
            llm,
            [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=json.dumps(
                        {
                            "system_definition": (
                                state.system_definition.model_dump()
                                if state.system_definition
                                else None
                            )
                        }
                    )
                ),
            ],
        ).content
    else:
        question = state.question

    first_user_input = interrupt({"question": question, "graph_name": graph_name})

    function_id = first_user_input.get("raw_user_input")
    selected_function = next(
        (f for f in state.system_definition.system_functions if f.id == function_id),
        None,
    )

    return state.model_copy(
        update={
            "graph_name": graph_name,
            "question": question,
            "raw_user_input": json.dumps(
                {
                    "system_description": state.system_definition.system_description,
                    "system_function": selected_function.model_dump(),
                    "assumptions": state.system_definition.assumptions,
                }
            ),
        }
    )
