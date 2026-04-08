from state.facility_layout_graph import FacilityLayoutState
from langgraph.types import interrupt


def collect_input_node(state: FacilityLayoutState, config):
    question = "Please provide system description, system functions, and assumptions in JSON format."
    graph_name = getattr(state.execution_context, "current_graph", None)

    user_input = interrupt({"question": question, "graph_name": graph_name})

    return state.model_copy(
        update={
            "raw_user_input": user_input["raw_user_input"],
            "graph_name": graph_name,
        }
    )
