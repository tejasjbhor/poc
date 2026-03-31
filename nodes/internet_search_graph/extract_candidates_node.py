import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS
from utils.json_utils import coerce_json


def extract_candidates_node(state: InternetSearchState, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_extract_candidates"]

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "system_understanding": state.get("system_understanding"),
                        "raw_results": state.get("raw_results"),
                    }
                )
            ),
        ],
    )

    parsed = coerce_json(response.content)

    return {
        "candidates": parsed.get("candidates", parsed),
        "step": "RANK_CANDIDATES",
    }
