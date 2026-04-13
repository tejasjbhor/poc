from functools import partial

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from helpers.log_node import log_node
from nodes.requirement_generation_graph.generate_requirements_node import (
    generate_requirements_node,
)
from nodes.requirement_generation_graph.load_system_context_node import (
    load_system_context_node,
)
from nodes.requirement_generation_graph.request_function_selection_node import (
    request_function_selection_node,
)
from nodes.requirement_generation_graph.request_requirements_review_node import (
    request_requirements_review_node,
)
from nodes.requirement_generation_graph.update_requirements_node import (
    update_requirements_node,
)
from state.requirement_generation_graph import RequirementGenerationState


def build_requirement_generation_graph(graph_name, llm):
    builder = StateGraph(RequirementGenerationState)

    builder.add_node(
        "LOAD_SYSTEM_CONTEXT",
        log_node(
            graph_name,
            "LOAD_SYSTEM_CONTEXT",
            load_system_context_node,
        ),
    )

    builder.add_node(
        "REQUEST_FUNCTION_SELECTION",
        log_node(
            graph_name,
            "REQUEST_FUNCTION_SELECTION",
            request_function_selection_node,
        ),
    )

    builder.add_node(
        "GENERATE_REQUIREMENTS",
        log_node(
            graph_name,
            "GENERATE_REQUIREMENTS",
            partial(generate_requirements_node, llm=llm),
        ),
    )

    builder.add_node(
        "REQUEST_REQUIREMENTS_REVIEW",
        log_node(
            graph_name,
            "REQUEST_REQUIREMENTS_REVIEW",
            request_requirements_review_node,
        ),
    )

    builder.add_node(
        "UPDATE_REQUIREMENTS",
        log_node(
            graph_name,
            "UPDATE_REQUIREMENTS",
            partial(update_requirements_node, llm=llm),
        ),
    )

    builder.add_edge(START, "LOAD_SYSTEM_CONTEXT")
    builder.add_edge("LOAD_SYSTEM_CONTEXT", "REQUEST_FUNCTION_SELECTION")
    builder.add_edge("REQUEST_FUNCTION_SELECTION", "GENERATE_REQUIREMENTS")
    builder.add_edge("GENERATE_REQUIREMENTS", "REQUEST_REQUIREMENTS_REVIEW")

    builder.add_conditional_edges(
        "REQUEST_REQUIREMENTS_REVIEW",
        lambda s: s["step"],
        {
            "UPDATE_REQUIREMENTS": "UPDATE_REQUIREMENTS",
            "FINAL": END,
        },
    )

    builder.add_edge("UPDATE_REQUIREMENTS", "REQUEST_REQUIREMENTS_REVIEW")

    checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)
