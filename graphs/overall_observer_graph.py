from langgraph.graph import StateGraph, START, END

from helpers.log_node import log_node

from nodes.overall_observer_graph.routing_decider_node import routing_decider_node
from registeries.agent_registry import get_all_agent_ids, resolve_callable
from state.overall_observer_graph import OverallObserverState
from langgraph.checkpoint.memory import InMemorySaver


def build_overall_observer_graph(graph_name, llm):
    builder = StateGraph(OverallObserverState)

    builder.add_node(
        "DECIDE_ROUTE",
        log_node(
            graph_name,
            "DECIDE_ROUTE",
            lambda s: routing_decider_node(s, llm),
        ),
    )

    # =========================
    # Nodes
    # =========================
    all_agent_ids = get_all_agent_ids()
    for agent_id in all_agent_ids:
        node_fn = resolve_callable(agent_id, llm)

        async def node_fn_bound(state, config, node_fn=node_fn):
            return await node_fn(state, config)

        builder.add_node(
            agent_id.upper(),
            log_node(
                graph_name,
                agent_id,
                node_fn_bound,
            ),
        )

    builder.add_edge(START, "DECIDE_ROUTE")

    builder.add_conditional_edges(
        "DECIDE_ROUTE",
        lambda s: s["next_step"] or "DECIDE_ROUTE",
        {
            "DECIDE_ROUTE": "DECIDE_ROUTE",
            "SYSTEM_DEFINITION": "SYSTEM_DEFINITION",
            "INTERNET_SEARCH": "INTERNET_SEARCH",
            "LAYOUT": "LAYOUT",
            "FINAL": END,
        },
    )

    checkpointer = InMemorySaver()

    return builder.compile(checkpointer=checkpointer)
