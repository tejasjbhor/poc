from state.facility_layout_graph import FacilityLayoutState


def hydrate_layout_graph_node(state: FacilityLayoutState, config):
    graph_name = getattr(state.execution_context, "current_graph", None)
    mode = state.execution_context.mode

    if mode == "standalone":
        return state.model_copy(
            update={
                "step": "COLLECT_INPUT",
                "graph_name": graph_name,
            }
        )

    def is_hydrated(state: FacilityLayoutState) -> bool:
        return any(
            [
                state.system_description,
                state.system_functions,  # empty list = False
                state.assumptions,
            ]
        )

    state_is_hydrated = is_hydrated(state)
    print(state_is_hydrated)

    if state_is_hydrated:
        return state.model_copy(
            update={
                "step": "COLLECT_CONSTRAINTS",
                "graph_name": graph_name,
            }
        )
    else:
        return state.model_copy(
            update={
                "step": (
                    "COLLECT_INPUT" if mode == "standalone" else "COLLECT_CONSTRAINTS"
                ),
                "graph_name": graph_name,
            }
        )
