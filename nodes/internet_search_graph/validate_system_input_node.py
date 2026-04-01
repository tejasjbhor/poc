import json

from langchain.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from helpers.interpret_user_input import is_done_user_input
from helpers.llm_safe_invoke import safe_llm_invoke
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS


def validate_system_input_node(state: InternetSearchState, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_validate_system_input"]

    system_understanding = state.get("system_understanding")

    question = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(content=json.dumps({"system_understanding": system_understanding})),
        ],
    ).content

    user_action = interrupt(question)

    if not is_done_user_input(user_action["raw_user_input"]):
        return {
            "system_understanding": user_action["raw_user_input"],
            "step": "INTERPRET_SYSTEM_INPUT",
        }

    return {
        "step": "GENERATE_QUERIES",
    }
