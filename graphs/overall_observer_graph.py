from functools import partial

from langgraph.graph import StateGraph, START, END

from helpers.log_node import log_node

from nodes.overall_observer_graph.routing_decider_node import routing_decider_node
from nodes.shared_nodes.execution_context_definition_node import (
    execution_context_definition_node,
)
from nodes.shared_nodes.normalize_execution_context_node import (
    normalize_execution_context_node,
)
from registeries.agent_registry import get_all_agent_ids, resolve_callable
from state.overall_observer_graph import OverallObserverState
from langgraph.checkpoint.memory import InMemorySaver


def build_overall_observer_graph(graph_name, llm):
    builder = StateGraph(OverallObserverState)

    builder.add_node(
        "EXECUTION_CONTEXT_DEFINITION",
        log_node(
            graph_name,
            "EXECUTION_CONTEXT_DEFINITION",
            partial(execution_context_definition_node),
        ),
    )

    builder.add_node(
        "DECIDE_ROUTE",
        log_node(
            graph_name,
            "DECIDE_ROUTE",
            partial(routing_decider_node, llm=llm),
        ),
    )

    builder.add_node(
        "NORMALIZE_EXECUTION_CONTEXT",
        log_node(
            graph_name,
            "NORMALIZE_EXECUTION_CONTEXT",
            partial(normalize_execution_context_node),
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

    builder.add_edge(START, "EXECUTION_CONTEXT_DEFINITION")
    builder.add_edge("EXECUTION_CONTEXT_DEFINITION", "DECIDE_ROUTE")

    builder.add_conditional_edges(
        "DECIDE_ROUTE",
        lambda s: s.next_step or "DECIDE_ROUTE",
        {
            "DECIDE_ROUTE": "DECIDE_ROUTE",
            "SYSTEM_DEFINITION": "SYSTEM_DEFINITION",
            "INTERNET_SEARCH": "INTERNET_SEARCH",
            "LAYOUT": "LAYOUT",
            "FINAL": END,
        },
    )

    for n in all_agent_ids:
        builder.add_edge(n.upper(), "NORMALIZE_EXECUTION_CONTEXT")

    builder.add_edge("NORMALIZE_EXECUTION_CONTEXT", "DECIDE_ROUTE")

    checkpointer = InMemorySaver()

    return builder.compile(checkpointer=checkpointer)
