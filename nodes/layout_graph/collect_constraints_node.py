import json

from helpers.interpret_user_input import is_done_user_input
from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityLayoutState
from langchain.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt


from langchain_core.messages import SystemMessage, HumanMessage
import json


def collect_constraints_node(state: FacilityLayoutState, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_collect_layout_constraints"]

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
                        "constraints": state.get("constraints", {}),
                        "constraints_user_feedback": state.get(
                            "constraints_user_feedback", ""
                        ),
                    }
                )
            ),
        ],
    )

    user_refinment_feedback = interrupt(response.content)

    # 3. Detect if user wants to stop refinement
    if is_done_user_input(user_refinment_feedback["raw_user_input"]):
        return {
            "constraints": json.loads(response.content),
            "constraints_user_feedback": user_refinment_feedback["raw_user_input"]
            or "",
            "step": "GENERATE_LAYOUT",
        }

    # 3. Return state update (ONLY place where state changes)
    return {
        "constraints": json.loads(response.content),
        "constraints_user_feedback": user_refinment_feedback["raw_user_input"] or "",
        "step": "REFINE_CONSTRAINTS",
    }
