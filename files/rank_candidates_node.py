import json
from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS
from state.internet_search_graph import InternetSearchState
from utils.json_utils import coerce_json


def rank_candidates_node(state: InternetSearchState, config, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_rank_candidates"]

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "system_understanding": state.get("system_understanding"),
                        "candidates": state.get("candidates"),
                    }
                )
            ),
        ],
    )

    parsed = coerce_json(response.content)

    return {
        "ranked_candidates": parsed,
        "graph_name": config["configurable"]["graph_name"],
        "step": "FINAL_VALIDATION",
    }
