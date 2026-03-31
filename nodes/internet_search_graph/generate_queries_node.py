import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS
from utils.json_utils import coerce_json


def generate_queries_node(state: InternetSearchState, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_generate_queries"]

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(content=json.dumps(state.get("system_understanding", {}))),
        ],
    )

    parsed = coerce_json(response.content)

    return {
        "queries": parsed.get("queries", []),
        "step": "VALIDATE_QUERIES",
    }
