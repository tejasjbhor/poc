import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS
from utils.json_utils import coerce_json


def generate_queries_node(state: InternetSearchState, config, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_generate_queries"]

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "system_understanding": state.get("system_understanding", {}),
                        "queries": state.get("queries", {}),
                        "user_queries_refinement": state.get(
                            "user_queries_refinment", ""
                        ),
                    }
                )
            ),
        ],
    )

    parsed = coerce_json(response.content)

    return {
        "queries": parsed.get("queries", []),
        "graph_name": config["configurable"]["graph_name"],
        "step": "VALIDATE_QUERIES",
    }
