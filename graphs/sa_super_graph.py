from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from helpers.log_node import log_node
from nodes.sa_super_graph.fetch_graph_context_node import fetch_graph_context_node
from nodes.sa_super_graph.super_observer_llm_node import super_observer_llm_node
from state.sa_super_graph import SaSuperGraphState


def build_sa_super_graph(graph_name: str, llm):
    builder = StateGraph(SaSuperGraphState)

    builder.add_node(
        "FETCH_GRAPH_CONTEXT",
        log_node(
            graph_name,
            "FETCH_GRAPH_CONTEXT",
            fetch_graph_context_node,
        ),
    )
    builder.add_node(
        "SUPER_OBSERVER_LLM",
        log_node(
            graph_name,
            "SUPER_OBSERVER_LLM",
            lambda s: super_observer_llm_node(s, llm),
        ),
    )

    builder.add_edge(START, "FETCH_GRAPH_CONTEXT")
    builder.add_edge("FETCH_GRAPH_CONTEXT", "SUPER_OBSERVER_LLM")
    builder.add_edge("SUPER_OBSERVER_LLM", END)

    checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)
