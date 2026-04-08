from functools import partial

from langgraph.graph import StateGraph, START, END

from helpers.log_node import log_node

from nodes.layout_graph.collect_constraints_node import collect_constraints_node
from nodes.layout_graph.generate_layout_node import generate_layout_node
from nodes.layout_graph.hydrate_layout_graph_node import hydrate_layout_graph_node
from nodes.layout_graph.normalize_input_node import normalize_input_node
from nodes.layout_graph.collect_input_node import collect_input_node
from nodes.layout_graph.review_layout_node import review_layout_node
from nodes.shared_nodes.execution_context_definition_node import (
    execution_context_definition_node,
)
from state.facility_layout_graph import FacilityLayoutState
from langgraph.checkpoint.memory import InMemorySaver


def build_facility_layout_graph(graph_name, llm):
    builder = StateGraph(FacilityLayoutState)

    # =========================
    # Nodes
    # =========================

    builder.add_node(
        "EXECUTION_CONTEXT_DEFINITION",
        log_node(
            graph_name,
            "EXECUTION_CONTEXT_DEFINITION",
            partial(execution_context_definition_node),
        ),
    )

    builder.add_node(
        "HYDRATE_LAYOUT",
        log_node(
            graph_name,
            "HYDRATE_LAYOUT",
            partial(hydrate_layout_graph_node),
        ),
    )

    builder.add_node(
        "COLLECT_INPUT",
        log_node(
            graph_name,
            "COLLECT_INPUT",
            partial(collect_input_node),
        ),
    )

    builder.add_node(
        "NORMALIZE_INPUT",
        log_node(
            graph_name,
            "NORMALIZE_INPUT",
            partial(normalize_input_node),
        ),
    )

    builder.add_node(
        "COLLECT_CONSTRAINTS",
        log_node(
            graph_name,
            "COLLECT_CONSTRAINTS",
            partial(collect_constraints_node, llm=llm),
        ),
    )

    builder.add_node(
        "GENERATE_LAYOUT",
        log_node(
            graph_name,
            "GENERATE_LAYOUT",
            partial(generate_layout_node, llm=llm),
        ),
    )

    builder.add_node(
        "REVIEW_LAYOUT",
        log_node(
            graph_name,
            "REVIEW_LAYOUT",
            partial(review_layout_node, llm=llm),
        ),
    )

    # =========================
    # Entry
    # =========================

    builder.add_edge(START, "EXECUTION_CONTEXT_DEFINITION")
    builder.add_edge("EXECUTION_CONTEXT_DEFINITION", "HYDRATE_LAYOUT")

    # =========================
    # Flow
    # =========================

    builder.add_edge("COLLECT_INPUT", "NORMALIZE_INPUT")

    builder.add_edge("NORMALIZE_INPUT", "COLLECT_CONSTRAINTS")

    builder.add_edge("GENERATE_LAYOUT", "REVIEW_LAYOUT")

    # =========================
    # Conditional routing (feedback loop)
    # =========================
    builder.add_conditional_edges(
        "HYDRATE_LAYOUT",
        lambda s: s.step,
        {
            "COLLECT_INPUT": "COLLECT_INPUT",
            "COLLECT_CONSTRAINTS": "COLLECT_CONSTRAINTS",
        },
    )

    builder.add_conditional_edges(
        "COLLECT_CONSTRAINTS",
        lambda s: s.step,
        {
            "GENERATE_LAYOUT": "GENERATE_LAYOUT",
            "REFINE_CONSTRAINTS": "COLLECT_CONSTRAINTS",
        },
    )

    builder.add_conditional_edges(
        "REVIEW_LAYOUT",
        lambda s: s.step,
        {
            "REFINE_LAYOUT": "GENERATE_LAYOUT",
            "FINAL": END,
        },
    )

    # =========================
    # Compile
    # =========================

    checkpointer = InMemorySaver()

    return builder.compile(checkpointer=checkpointer)
