import json

from langgraph.types import interrupt

from langchain.messages import HumanMessage, SystemMessage

from helpers.interpret_user_input import is_done_user_input
from helpers.llm_safe_invoke import safe_llm_invoke
from state.internet_search_graph import InternetSearchState
from prompts.internet_search_prompts import INTERNET_SEARCH_PROMPTS


def final_validation_node(state: InternetSearchState, llm):
    # prompt = INTERNET_SEARCH_PROMPTS["prompt_final_validation"]

    # question = safe_llm_invoke(
    #     llm,
    #     [
    #         SystemMessage(content=prompt),
    #         HumanMessage(
    #             content=json.dumps(
    #                 {
    #                     "system_understanding": state.get("system_understanding"),
    #                     "ranked_candidates": state.get("ranked_candidates"),
    #                 }
    #             )
    #         ),
    #     ],
    # ).content

    # question = "Validate the ranked results, describe any modifications you wish to have, or type done to end the process."

    # user_action = interrupt(question)
    
    # if not is_done_user_input(user_action["raw_user_input"]):
    #     return {
    #         "ranked_candidates": user_action["raw_user_input"],
    #         "step": "GENERATE_QUERIES",
    #     }

    return {
        "step": "FINAL",
    }
