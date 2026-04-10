import json
from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS
from schemas.graphs.internet_search.output import InternetSearchOutput
from state.internet_search_graph import InternetSearchState
from utils.json_utils import coerce_json


def rank_candidates_node(state: InternetSearchState, config, llm):
    prompt = INTERNET_SEARCH_PROMPTS["prompt_rank_candidates"]
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
                        "candidates": state.candidates,
                    }
                )
            ),
        ],
    )

    parsed = coerce_json(response.content)

    return state.model_copy(
        update={
            "graph_name": graph_name,
            "internet_search_outcome": (
                state.internet_search_outcome.model_copy(
                    update={"ranked_candidates": parsed}
                )
                if state.internet_search_outcome
                else InternetSearchOutput(ranked_candidates=parsed)
            ),
        }
    )
