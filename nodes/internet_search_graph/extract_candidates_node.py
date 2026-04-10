import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS
from utils.json_utils import coerce_json


def extract_candidates_node(state: InternetSearchState, config, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_extract_candidates"]
    graph_name = getattr(state.execution_context, "current_graph", None)

    system_understanding = getattr(
        state.internet_search_outcome, "system_understanding", None
    )

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "system_understanding": system_understanding,
                        "candidates": state.raw_results or {},
                    }
                )
            ),
        ],
    )
    parsed = coerce_json(response.content)

    return state.model_copy(
        update={
            "candidates": parsed,
            "graph_name": graph_name,
        }
    )
