from state.facility_layout_graph import FacilityState


def route_from_step(state: FacilityState):
    return state.get("last_step")