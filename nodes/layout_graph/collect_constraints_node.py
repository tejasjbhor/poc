import json

from helpers.interpret_user_input import is_done_user_input
from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.facility_layout_prompts import FACILITY_LAYOUT_PROMPTS
from schemas.domain.layout import LayoutConstraints
from schemas.graphs.layout.output import LayoutOutput
from state.facility_layout_graph import FacilityLayoutState
from langchain.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt


from utils.json_utils import coerce_json


def collect_constraints_node(state: FacilityLayoutState, config, llm):
    prompt = FACILITY_LAYOUT_PROMPTS["prompt_collect_layout_constraints"]
    graph_name = getattr(state.execution_context, "current_graph", None)

    previous_layout = state.final_layout or LayoutOutput()
    layout_constraints = previous_layout.layout_constraints

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "system_definition": (
                            state.system_definition.model_dump()
                            if state.system_definition
                            else None
                        ),
                        "layout_constraints": (
                            layout_constraints.model_dump()
                            if layout_constraints
                            else None
                        ),
                        "constraints_user_feedback": state.constraints_user_feedback
                        or "",
                    }
                )
            ),
        ],
        response_model=LayoutConstraints,
    )

    user_refinment_feedback = interrupt(
        {
            "question": response,
            "graph_name": graph_name,
        }
    )

    user_input = user_refinment_feedback.get("raw_user_input", "")

    return state.model_copy(
        update={
            "final_layout": (
                state.final_layout.model_copy(update={"layout_constraints": response})
                if state.final_layout
                else LayoutOutput(layout_constraints=response)
            ),
            "constraints_user_feedback": user_input or "",
            "graph_name": graph_name,
            "step": (
                "GENERATE_LAYOUT"
                if is_done_user_input(user_input)
                else "REFINE_CONSTRAINTS"
            ),
        }
    )
