from langchain.messages import HumanMessage
from langgraph.types import interrupt

from helpers.interpret_user_input import is_done_user_input
from helpers.llm_safe_invoke import safe_llm_invoke
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS


def validate_queries_node(state: InternetSearchState, config, llm):
    question = "Please validate the generated queries. You may add or remove by resquesting in the chat, if not, type done to proceed."

    user_action = interrupt(
        {"question": question, "graph_name": config["configurable"]["graph_name"]}
    )

    if not is_done_user_input(user_action["raw_user_input"]):
        return {
            "user_queries_refinment": user_action["raw_user_input"],
            "step": "GENERATE_QUERIES",
        }

    return {
        "graph_name": config["configurable"]["graph_name"],
        "step": "SEARCH_SOURCES",
    }
