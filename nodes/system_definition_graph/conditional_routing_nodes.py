from state.system_definition_graph import SystemDefinitionState


def route_from_step(state: SystemDefinitionState):
    return state.get("last_step")
