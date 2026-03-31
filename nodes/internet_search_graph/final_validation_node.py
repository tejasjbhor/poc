from langgraph.types import interrupt

from langchain.messages import HumanMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS


def final_validation_node(state: InternetSearchState, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_final_validation"]

    question = safe_llm_invoke(
        llm,
        [HumanMessage(content=prompt)],
    ).content

    user_action = interrupt(
        {
            "question": question,
            "ranked_candidates": state.get("ranked_candidates"),
        }
    )

    if user_action["action"] == "edit":
        return {
            "ranked_candidates": user_action["data"],
            "step": "FINAL_VALIDATION",
        }

    return {
        "step": "END",
    }
