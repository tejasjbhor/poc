from langchain.messages import HumanMessage
from langgraph.types import interrupt

from helpers.llm_safe_invoke import safe_llm_invoke
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS


def validate_system_input_node(state: InternetSearchState, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_validate_system_input"]

    question = safe_llm_invoke(
        llm,
        [HumanMessage(content=prompt)],
    ).content

    user_action = interrupt(
        {
            "question": question,
            "system_understanding": state.get("system_understanding"),
        }
    )

    if user_action["action"] == "edit":
        return {
            "system_understanding": user_action["data"],
            "step": "VALIDATE_SYSTEM_INPUT",
        }

    return {
        "step": "GENERATE_QUERIES",
    }
