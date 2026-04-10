import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from schemas.graphs.internet_search.output import InternetSearchOutput
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS
from utils.json_utils import coerce_json


def generate_queries_node(state: InternetSearchState, config, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_generate_queries"]
    graph_name = getattr(state.execution_context, "current_graph", None)
    internet_search_outcome = state.internet_search_outcome or InternetSearchOutput()

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "system_understanding": internet_search_outcome.system_understanding,
                        "queries": internet_search_outcome.queries,
                        "user_queries_refinement": state.user_queries_refinment or "",
                    }
                )
            ),
        ],
    )

    parsed = coerce_json(response.content)

    queries = parsed.get("queries", [])

    if isinstance(queries, dict):
        queries = list(queries.values())

    return state.model_copy(
        update={
            "graph_name": graph_name,
            "internet_search_outcome": (
                state.internet_search_outcome.model_copy(update={"queries": queries})
                if state.internet_search_outcome
                else InternetSearchOutput(queries=queries)
            ),
        }
    )
