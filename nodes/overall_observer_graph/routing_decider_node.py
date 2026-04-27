from datetime import datetime

from helpers.overall_observer_router_helper import manual_routing
from registeries.agent_registry import AgentRegistry
from state.overall_observer_graph import OverallObserverState


def routing_decider_node(state: OverallObserverState, config, llm):
    execution_stack = state.execution_stack or []

    graph_name = getattr(state.execution_context, "current_graph", None)

    agent_registry: AgentRegistry = (
        config.get("configurable").get("runtime").get("agent_registry")
    )

    if execution_stack:
        task = execution_stack[-1]

        # -------------------------
        # PENDING → go to resolver
        # -------------------------
        if task.status == "pending":
            task.status = "resolving"

            return state.model_copy(
                update={
                    "next_step": task.hydration_resolver,
                    "last_step": state.step,
                    "step": state.next_step,
                    "execution_stack": execution_stack,
                    "_emit": datetime.now(),
                    "graph_name": graph_name,
                }
            )

        # -------------------------
        # RETURNING → go back to requester
        # -------------------------
        elif task.status == "returning":
            return state.model_copy(
                update={
                    "next_step": task.hydration_requester,
                    "last_step": state.step,
                    "step": state.next_step,
                    "_emit": datetime.now(),
                    "graph_name": graph_name,
                }
            )

    # -------------------------
    # Default manual routing
    # -------------------------
    return manual_routing(state, llm, graph_name, agent_registry)
