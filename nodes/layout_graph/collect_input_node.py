from state.facility_layout_graph import FacilityLayoutState
from langgraph.types import interrupt


def collect_input_node(state: FacilityLayoutState, config):
    question = "Please provide system description, system functions, and assumptions in JSON format."

    user_input = interrupt(
        {"question": question, "graph_name": config["configurable"]["graph_name"]}
    )

    return {
        "raw_user_input": user_input["raw_user_input"],
        "graph_name": config["configurable"]["graph_name"],
    }
