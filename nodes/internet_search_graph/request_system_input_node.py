from langgraph.types import interrupt
from langchain.messages import HumanMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS


def request_system_input_node(state: InternetSearchState, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_request_system_input"]

    if "question" not in state:
        question = safe_llm_invoke(
            llm,
            [HumanMessage(content=prompt)],
        ).content
    else:
        question = state["question"]

    first_user_input = interrupt(question)

    return {
        "question": question,
        "raw_user_input": first_user_input["raw_user_input"],
        "step": "INTERPRET_SYSTEM_INPUT",
    }
