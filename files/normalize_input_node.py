import json

from state.facility_layout_graph import FacilityLayoutState


def normalize_input_node(state: FacilityLayoutState, config):

    raw = state["raw_user_input"]

    # if coming from interrupt, ensure string/dict handling
    if isinstance(raw, str):
        raw = json.loads(raw)

    return {
        "system_description": raw.get("system_description", ""),
        "system_functions": raw.get("system_functions", []),
        "graph_name": config["configurable"]["graph_name"],
        "assumptions": raw.get("assumptions", []),
    }
