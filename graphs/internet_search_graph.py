from functools import partial

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from helpers.log_node import log_node
from nodes.internet_search_graph.extract_candidates_node import extract_candidates_node
from nodes.internet_search_graph.final_validation_node import final_validation_node
from nodes.internet_search_graph.generate_queries_node import generate_queries_node
from nodes.internet_search_graph.interpret_system_input_node import (
    interpret_system_input_node,
)
from nodes.internet_search_graph.rank_candidates_node import rank_candidates_node
from nodes.internet_search_graph.request_system_input_node import (
    request_system_input_node,
)
from nodes.internet_search_graph.search_sources_node import search_sources_node
from nodes.internet_search_graph.validate_queries_node import validate_queries_node
from nodes.internet_search_graph.validate_system_input_node import (
    validate_system_input_node,
)
from nodes.shared_nodes.context_definition_node import context_definition_node
from state.internet_search_graph import InternetSearchState


def build_internet_search_graph(graph_name, llm):
    builder = StateGraph(InternetSearchState)

    # =========================
    # Nodes
    # =========================

    builder.add_node(
        "EXECUTION_CONTEXT_DEFINITION",
        log_node(
            graph_name,
            "EXECUTION_CONTEXT_DEFINITION",
            partial(context_definition_node),
        ),
    )

    builder.add_node(
        "REQUEST_SYSTEM_INPUT",
        log_node(
            graph_name,
            "REQUEST_SYSTEM_INPUT",
            partial(request_system_input_node, llm=llm),
        ),
    )

    builder.add_node(
        "INTERPRET_SYSTEM_INPUT",
        log_node(
            graph_name,
            "INTERPRET_SYSTEM_INPUT",
            partial(interpret_system_input_node, llm=llm),
        ),
    )

    builder.add_node(
        "VALIDATE_SYSTEM_INPUT",
        log_node(
            graph_name,
            "VALIDATE_SYSTEM_INPUT",
            partial(validate_system_input_node, llm=llm),
        ),
    )

    builder.add_node(
        "GENERATE_QUERIES",
        log_node(
            graph_name, "GENERATE_QUERIES", partial(generate_queries_node, llm=llm)
        ),
    )

    builder.add_node(
        "VALIDATE_QUERIES",
        log_node(
            graph_name, "VALIDATE_QUERIES", partial(validate_queries_node, llm=llm)
        ),
    )

    async def search_sources_bound(state, config):
        return await search_sources_node(state, config)

    builder.add_node(
        "SEARCH_SOURCES",
        log_node(
            graph_name,
            "SEARCH_SOURCES",
            search_sources_bound,
        ),
    )

    builder.add_node(
        "EXTRACT_CANDIDATES",
        log_node(
            graph_name, "EXTRACT_CANDIDATES", partial(extract_candidates_node, llm=llm)
        ),
    )

    builder.add_node(
        "RANK_CANDIDATES",
        log_node(graph_name, "RANK_CANDIDATES", partial(rank_candidates_node, llm=llm)),
    )

    builder.add_node(
        "FINAL_VALIDATION",
        log_node(
            graph_name, "FINAL_VALIDATION", partial(final_validation_node, llm=llm)
        ),
    )

    # =========================
    # Entry
    # =========================
    builder.add_edge(START, "EXECUTION_CONTEXT_DEFINITION")
    builder.add_edge("EXECUTION_CONTEXT_DEFINITION", "REQUEST_SYSTEM_INPUT")

    # =========================
    # Linear Flow
    # =========================

    builder.add_edge("REQUEST_SYSTEM_INPUT", "INTERPRET_SYSTEM_INPUT")
    builder.add_edge("INTERPRET_SYSTEM_INPUT", "VALIDATE_SYSTEM_INPUT")

    builder.add_edge("GENERATE_QUERIES", "VALIDATE_QUERIES")

    builder.add_edge("SEARCH_SOURCES", "EXTRACT_CANDIDATES")
    builder.add_edge("EXTRACT_CANDIDATES", "RANK_CANDIDATES")
    builder.add_edge("RANK_CANDIDATES", "FINAL_VALIDATION")

    # =========================
    # Conditional Routing (STEP-DRIVEN)
    # =========================

    # 🔁 System understanding loop
    builder.add_conditional_edges(
        "VALIDATE_SYSTEM_INPUT",
        lambda s: s["step"],
        {
            "INTERPRET_SYSTEM_INPUT": "INTERPRET_SYSTEM_INPUT",  # user edited → re-interpret
            "GENERATE_QUERIES": "GENERATE_QUERIES",  # approved → continue
        },
    )

    # 🔁 Query validation loop
    builder.add_conditional_edges(
        "VALIDATE_QUERIES",
        lambda s: s["step"],
        {
            "GENERATE_QUERIES": "GENERATE_QUERIES",  # refine queries
            "SEARCH_SOURCES": "SEARCH_SOURCES",  # approved
        },
    )

    # 🔁 Final validation loop (VERY IMPORTANT)
    builder.add_conditional_edges(
        "FINAL_VALIDATION",
        lambda s: s["step"],
        {
            "GENERATE_QUERIES": "GENERATE_QUERIES",  # refine everything
            "SEARCH_SOURCES": "SEARCH_SOURCES",  # rerun search
            "FINAL": END,  # done
        },
    )

    # =========================
    # Checkpointer
    # =========================

    checkpointer = InMemorySaver()

    return builder.compile(checkpointer=checkpointer)
