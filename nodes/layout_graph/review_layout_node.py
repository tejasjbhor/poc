from helpers.interpret_user_input import is_done_user_input
from state.facility_layout_graph import FacilityLayoutState
from langgraph.types import interrupt


def review_layout_node(state: FacilityLayoutState, config, llm):
    question = "Please review carefully the proposed layout, and give your feedback. If all is good, type done."
    graph_name = getattr(state.execution_context, "current_graph", None)

    layout_user_feedback = interrupt({"question": question, "graph_name": graph_name})

    user_input = layout_user_feedback.get("raw_user_input", "")

    return state.model_copy(
        update={
            "layout_user_feedback": user_input,
            "constraints_user_feedback": user_input or "",
            "graph_name": graph_name,
            "step": ("FINAL" if is_done_user_input(user_input) else "REFINE_LAYOUT"),
        }
    )
