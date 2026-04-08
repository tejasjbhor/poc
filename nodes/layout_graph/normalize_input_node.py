import json

from state.facility_layout_graph import FacilityLayoutState


def normalize_input_node(state: FacilityLayoutState, config):
    graph_name = getattr(state.execution_context, "current_graph", None)

    def safe_parse_raw(raw):
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw.strip():
            try:
                return json.loads(raw)
            except Exception:
                return {}
        return {}

    raw = safe_parse_raw(state.raw_user_input)

    return state.model_copy(
        update={
            "system_description": raw.get("system_description", ""),
            "system_functions": raw.get("system_functions", []),
            "graph_name": graph_name,
            "assumptions": raw.get("assumptions", []),
        }
    )
