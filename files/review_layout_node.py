from helpers.interpret_user_input import is_done_user_input
from state.facility_layout_graph import FacilityLayoutState
from langgraph.types import interrupt


def review_layout_node(state: FacilityLayoutState, config, llm):
    question = "Please review carefully the proposed layout, and give your feedback. If all is good, type done."

    layout_user_feedback = interrupt(
        {"question": question, "graph_name": config["configurable"]["graph_name"]}
    )

    # 3. Detect if user wants to stop refinement
    if is_done_user_input(layout_user_feedback["raw_user_input"]):
        return {
            "layout_user_feedback": layout_user_feedback["raw_user_input"],
            "graph_name": config["configurable"]["graph_name"],
            "step": "FINAL",
        }

    return {
        "layout_user_feedback": layout_user_feedback["raw_user_input"],
        "graph_name": config["configurable"]["graph_name"],
        "step": "REFINE_LAYOUT",
    }
