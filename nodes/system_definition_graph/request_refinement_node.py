import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.interpret_user_input import is_done_user_input
from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from schemas.graphs.system_definition.output import SystemDefinitionOutput
from state.system_definition_graph import SystemDefinitionState

from langgraph.types import interrupt


def request_refinement_node(state: SystemDefinitionState, config, llm):
    graph_name = getattr(state.execution_context, "current_graph", None)

    # 1. Avoid recomputation on resume
    if state.refinement_question is None:
        prompt = SYSTEM_DEFINITION_PROMPTS["prompt_request_function_refinement"]

        response = safe_llm_invoke(
            llm,
            [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=json.dumps(
                        {
                            "current_system_definition": (
                                state.system_definition.model_dump()
                                if state.system_definition
                                else None
                            ),
                        }
                    )
                ),
            ],
        )

        question = response.content

    else:
        question = state.refinement_question

    # 2. Interrupt (pause)
    user_refinment_feedback = interrupt(
        {"question": question, "graph_name": graph_name}
    )

    # 3. Detect if user wants to stop refinement
    if is_done_user_input(user_refinment_feedback["raw_user_input"]):
        return state.model_copy(
            update={
                "refinement_question": question,
                "user_refinment_feedback": user_refinment_feedback["raw_user_input"],
                "step": "FINAL",
                "system_definition": state.system_definition,
                "graph_name": graph_name,
            }
        )

    # 3. Return state update (ONLY place where state changes)
    return state.model_copy(
        update={
            "refinement_question": question,
            "user_refinment_feedback": user_refinment_feedback["raw_user_input"],
            "step": "UPDATE_SYSTEM_FUNCTIONS",
            "graph_name": graph_name,
        }
    )
