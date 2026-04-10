import json

from langchain.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from helpers.interpret_user_input import is_done_user_input
from helpers.llm_safe_invoke import safe_llm_invoke
from schemas.graphs.internet_search.output import InternetSearchOutput
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS


def validate_system_input_node(state: InternetSearchState, config, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_validate_system_input"]
    graph_name = getattr(state.execution_context, "current_graph", None)
    internet_search_outcome = (
        state.internet_search_outcome or InternetSearchOutput()
    )
    system_understanding = internet_search_outcome.system_understanding

    question = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "system_understanding": system_understanding,
                    }
                )
            ),
        ],
    ).content

    user_action = interrupt({"question": question, "graph_name": graph_name})

    if not is_done_user_input(user_action["raw_user_input"]):
        return state.model_copy(
            update={
                "graph_name": graph_name,
                "raw_user_input": user_action.get("raw_user_input"),
                "step": "INTERPRET_SYSTEM_INPUT",
            }
        )
    return state.model_copy(
        update={
            "graph_name": graph_name,
            "step": "GENERATE_QUERIES",
        }
    )
