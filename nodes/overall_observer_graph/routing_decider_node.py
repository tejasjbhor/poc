from helpers.overall_observer_router_helper import hydration_routing, manual_routing
from registeries.agent_registry import AgentRegistry
from state.overall_observer_graph import OverallObserverState


def routing_decider_node(state: OverallObserverState, config, llm):
    hydration_request = state.hydration_issues
    graph_name = getattr(state.execution_context, "current_graph", None)
    agent_registry: AgentRegistry = (
        config.get("configurable").get("runtime").get("agent_registry")
    )

    if hydration_request:
        return hydration_routing(state, llm, graph_name, agent_registry)

    return manual_routing(state, llm, graph_name, agent_registry)
