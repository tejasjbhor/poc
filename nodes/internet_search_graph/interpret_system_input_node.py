from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS
from utils.json_utils import coerce_json


def interpret_system_input_node(state: InternetSearchState, config, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_interpret_system_input"]

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(content=state.get("raw_user_input", "")),
        ],
    )

    parsed = coerce_json(response.content)

    return {
        "system_understanding": parsed,
        "step": "VALIDATE_SYSTEM_INPUT",
    }
