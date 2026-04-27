from functools import partial

from langgraph.graph import StateGraph, START, END

from helpers.log_node import log_node

from nodes.overall_observer_graph.routing_decider_node import routing_decider_node
from nodes.shared_nodes.execution_context_definition_node import (
    execution_context_definition_node,
)
from nodes.overall_observer_graph.normalize_execution_context_node import (
    normalize_execution_context_node,
)
from state.overall_observer_graph import OverallObserverState
from langgraph.checkpoint.memory import InMemorySaver


def build_overall_observer_graph(agents_registry, graph_name, llm):
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
            partial(normalize_execution_context_node, llm=llm),
        ),
    )

    # =========================
    # Nodes
    # =========================
    for agent in agents_registry.all():
        builder.add_node(
            agent.spec.agent_id.upper(),
            agent.as_node(llm, graph_name, log_node),
        )

    builder.add_edge(START, "EXECUTION_CONTEXT_DEFINITION")
    builder.add_edge("EXECUTION_CONTEXT_DEFINITION", "DECIDE_ROUTE")

    builder.add_conditional_edges(
        "DECIDE_ROUTE",
        lambda s: s.next_step or "DECIDE_ROUTE",
        agents_registry.get_route_map(),
    )

    for agent in agents_registry.all():
        builder.add_edge(
            agent.spec.agent_id.upper(),
            "NORMALIZE_EXECUTION_CONTEXT",
        )

    builder.add_edge("NORMALIZE_EXECUTION_CONTEXT", "DECIDE_ROUTE")

    checkpointer = InMemorySaver()

    return builder.compile(checkpointer=checkpointer)
