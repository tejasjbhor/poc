from langgraph.types import interrupt

from helpers.interpret_user_input import is_done_user_input
from state.internet_search_graph import InternetSearchState


def validate_queries_node(state: InternetSearchState, config, llm):
    question = "Please validate the generated queries. You may add or remove by resquesting in the chat, if not, type done to proceed."
    graph_name = getattr(state.execution_context, "current_graph", None)

    user_action = interrupt({"question": question, "graph_name": graph_name})

    if not is_done_user_input(user_action["raw_user_input"]):
        return state.model_copy(
            update={
                "user_queries_refinment": user_action["raw_user_input"],
                "step": "GENERATE_QUERIES",
            }
        )
    return state.model_copy(
        update={
            "graph_name": graph_name,
            "step": "SEARCH_SOURCES",
        }
    )
