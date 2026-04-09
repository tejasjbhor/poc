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

    def is_hydrated(layout_input: LayoutInput) -> bool:
        return any(
            [
                system_definition.system_description,
                system_definition.system_functions,  # empty list = False
                system_definition.assumptions,
            ]
        )

    state_is_hydrated = is_hydrated(system_definition)
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
