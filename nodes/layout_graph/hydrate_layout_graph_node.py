from schemas.graphs.layout.input import LayoutInput
from state.facility_layout_graph import FacilityLayoutState


def hydrate_layout_graph_node(state: FacilityLayoutState, config):
    graph_name = getattr(state.execution_context, "current_graph", None)
    mode = state.execution_context.mode
    system_definition: LayoutInput = state.system_definition or LayoutInput()

    if mode == "standalone":
        return state.model_copy(
            update={
                "step": "COLLECT_INPUT",
                "graph_name": graph_name,
            }
        )

    def get_missing_fields(sd: LayoutInput) -> list[str]:
        missing = []

        # --- schema-driven checks ---
        for field in sd.model_fields.keys():
            value = getattr(sd, field)

            if value is None:
                missing.append(field)
            elif isinstance(value, list) and len(value) == 0:
                missing.append(field)

        # --- domain rules ---
        if sd.assumptions and len(sd.assumptions) <= 1:
            missing.append("assumptions_too_few")

        if sd.system_functions:
            for i, f in enumerate(sd.system_functions):
                if f.surface_area == 0:
                    missing.append(f"function_{f.id or i}_surface_area_zero")

        return missing

    missing_fields = get_missing_fields(system_definition)

    print(missing_fields)

    if not missing_fields:
        return state.model_copy(
            update={
                "step": "COLLECT_CONSTRAINTS",
                "graph_name": graph_name,
            }
        )

    # Subgraph → escalate to main graph
    return state.model_copy(
        update={
            "step": "REQUEST_DATA_FROM_MAIN",
            "hydration_issues": missing_fields,
            "hydration_requester": graph_name,
            "graph_name": graph_name,
        }
    )
