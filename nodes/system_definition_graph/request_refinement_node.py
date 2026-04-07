import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.interpret_user_input import is_done_user_input
from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState

from langgraph.types import interrupt


def request_refinement_node(state: SystemDefinitionState, config, llm):
    # 1. Avoid recomputation on resume
    if "refinement_question" not in state:
        prompt = SYSTEM_DEFINITION_PROMPTS["prompt_request_function_refinement"]

        response = safe_llm_invoke(
            llm,
            [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=json.dumps(
                        {
                            "system_description": state.get("system_description"),
                            "system_functions": state.get("system_functions"),
                            "assumptions": state.get("assumptions", []),
                        }
                    )
                ),
            ],
        )

        question = response.content
    else:
        question = state["refinement_question"]

    # 2. Interrupt (pause)
    user_refinment_feedback = interrupt(
        {"question": question, "graph_name": config["configurable"]["graph_name"]}
    )

    # 3. Detect if user wants to stop refinement
    if is_done_user_input(user_refinment_feedback["raw_user_input"]):
        return {
            "refinement_question": question,
            "user_refinment_feedback": user_refinment_feedback,
            "step": "FINAL",
            "system_description": state.get("system_description"),
            "system_functions": state.get("system_functions"),
            "assumptions": state.get("assumptions", []),
            "graph_name": config["configurable"]["graph_name"]
        }

    # 3. Return state update (ONLY place where state changes)
    return {
        "refinement_question": question,
        "user_refinment_feedback": user_refinment_feedback,
        "step": "UPDATE_SYSTEM_FUNCTIONS",
        "graph_name": config["configurable"]["graph_name"]
    }
