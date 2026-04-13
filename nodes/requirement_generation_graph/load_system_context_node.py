from state.requirement_generation_graph import RequirementGenerationState


def load_system_context_node(state: RequirementGenerationState, config):
    graph_name = config["configurable"]["graph_name"]
    desc = (state.get("system_description") or "").strip()
    functions = state.get("system_functions") or []
    assumptions = state.get("assumptions") or []

    if not desc:
        raise ValueError("system_description is required")
    if not functions:
        raise ValueError("system_functions must be non-empty")
    if not isinstance(functions, list):
        raise ValueError("system_functions must be a list")

    return {
        "system_description": desc,
        "system_functions": functions,
        "assumptions": assumptions,
        "graph_name": graph_name,
    }
