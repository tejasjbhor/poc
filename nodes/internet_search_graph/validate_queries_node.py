from langchain.messages import HumanMessage
from langgraph.types import interrupt

from helpers.llm_safe_invoke import safe_llm_invoke
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS


def validate_queries_node(state: InternetSearchState, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_validate_queries"]

    question = safe_llm_invoke(
        llm,
        [HumanMessage(content=prompt)],
    ).content

    user_action = interrupt(
        {
            "question": question,
            "queries": state.get("queries"),
        }
    )

    if user_action["action"] == "edit":
        return {
            "queries": user_action["data"],
            "step": "VALIDATE_QUERIES",
        }

    return {
        "step": "SEARCH_SOURCES",
    }
