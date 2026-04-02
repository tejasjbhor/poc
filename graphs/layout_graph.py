from langgraph.graph import StateGraph, START, END

from helpers.log_node import log_node

from nodes.layout_graph.collect_constraints_node import collect_constraints_node
from nodes.layout_graph.generate_layout_node import generate_layout_node
from nodes.layout_graph.normalize_input_node import normalize_input_node
from nodes.layout_graph.collect_input_node import collect_input_node
from nodes.layout_graph.review_layout_node import review_layout_node
from state.facility_layout_graph import FacilityLayoutState
from langgraph.checkpoint.memory import InMemorySaver


def build_facility_layout_graph(graph_name, llm):
    builder = StateGraph(FacilityLayoutState)

    # =========================
    # Nodes
    # =========================

    builder.add_node(
        "COLLECT_INPUT",
        log_node(
            graph_name,
            "COLLECT_INPUT",
            lambda s: collect_input_node(s),
        ),
    )

    builder.add_node(
        "NORMALIZE_INPUT",
        log_node(
            graph_name,
            "NORMALIZE_INPUT",
            lambda s: normalize_input_node(s),
        ),
    )

    builder.add_node(
        "COLLECT_CONSTRAINTS",
        log_node(
            graph_name,
            "COLLECT_CONSTRAINTS",
            lambda s: collect_constraints_node(s, llm),
        ),
    )

    builder.add_node(
        "GENERATE_LAYOUT",
        log_node(
            graph_name,
            "GENERATE_LAYOUT",
            lambda s: generate_layout_node(s, llm),
        ),
    )

    builder.add_node(
        "REVIEW_LAYOUT",
        log_node(
            graph_name,
            "REVIEW_LAYOUT",
            lambda s: review_layout_node(s, llm),
        ),
    )

    # =========================
    # Entry
    # =========================

    builder.add_edge(START, "COLLECT_INPUT")

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
        "COLLECT_CONSTRAINTS",
        lambda s: s["step"],
        {
            "GENERATE_LAYOUT": "GENERATE_LAYOUT",
            "REFINE_CONSTRAINTS": "COLLECT_CONSTRAINTS",
        },
    )

    builder.add_conditional_edges(
        "REVIEW_LAYOUT",
        lambda s: s["step"],
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
