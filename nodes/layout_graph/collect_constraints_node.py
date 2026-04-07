import json

from helpers.interpret_user_input import is_done_user_input
from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from state.facility_layout_graph import FacilityLayoutState
from langchain.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt


from langchain_core.messages import SystemMessage, HumanMessage
import json

from utils.json_utils import coerce_json


def collect_constraints_node(state: FacilityLayoutState, config, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_collect_layout_constraints"]
    graph_name = state.get("execution_context").get("current_graph")

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
                        "layout_constraints": state.get("layout_constraints", {}),
                        "constraints_user_feedback": state.get(
                            "constraints_user_feedback", ""
                        ),
                    }
                )
            ),
        ],
    )

    try:
        layout_constraints = coerce_json(response.content)
    except Exception:
        layout_constraints = {}

    user_refinment_feedback = interrupt(
        {
            "question": layout_constraints,
            "graph_name": graph_name,
        }
    )

    # 3. Detect if user wants to stop refinement
    if is_done_user_input(user_refinment_feedback["raw_user_input"]):
        return {
            "layout_constraints": layout_constraints,
            "constraints_user_feedback": user_refinment_feedback["raw_user_input"]
            or "",
            "graph_name": graph_name,
            "step": "GENERATE_LAYOUT",
        }

    # 3. Return state update (ONLY place where state changes)
    return {
        "layout_constraints": layout_constraints,
        "constraints_user_feedback": user_refinment_feedback["raw_user_input"] or "",
        "graph_name": graph_name,
        "step": "REFINE_CONSTRAINTS",
    }
