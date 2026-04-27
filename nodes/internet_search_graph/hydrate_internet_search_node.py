from schemas.graphs.internet_search.input import InternetSearchInput
from schemas.graphs.layout.input import LayoutInput
from state.internet_search_graph import InternetSearchState


def hydrate_internet_search_node(state: InternetSearchState, config):
    graph_name = getattr(state.execution_context, "current_graph", None)
    mode = state.execution_context.mode
    system_definition: InternetSearchInput = (
        state.system_definition or InternetSearchInput()
    )

    if mode == "standalone":
        return state.model_copy(
            update={
                "step": "REQUEST_SYSTEM_INPUT",
                "graph_name": graph_name,
            }
        )

    def get_missing_fields(sd: InternetSearchInput) -> list[str]:
        missing = []

        # --- schema-driven checks ---
        for field in sd.model_fields.keys():
            value = getattr(sd, field)

            if value is None:
                missing.append(field)
            elif isinstance(value, list) and len(value) == 0:
                missing.append(field)

        return missing

    missing_fields = get_missing_fields(system_definition)

    if not missing_fields:
        return state.model_copy(
            update={
                "step": "COLLECT_FUNCTION_INPUT",
                "graph_name": graph_name,
            }
        )

    # Subgraph → escalate to main graph
    return state.model_copy(
        update={
            "step": "REQUEST_DATA_FROM_MAIN",
            "hydration_issues": missing_fields,
            "hydration_requester": graph_name.upper(),
            "graph_name": graph_name,
        }
    )
