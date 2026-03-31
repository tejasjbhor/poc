from langgraph.graph import StateGraph, START, END

from helpers.log_node import log_node

from nodes.system_definition_graph.request_refinement_node import (
    request_refinement_node,
)
from nodes.system_definition_graph.request_system_input_node import (
    request_system_input_node,
)
from nodes.system_definition_graph.interpret_system_input_node import (
    interpret_system_input_node,
)
from nodes.system_definition_graph.update_system_functions_node import (
    update_system_functions_node,
)
from state.system_definition_graph import SystemDefinitionState
from langgraph.checkpoint.memory import InMemorySaver


def build_system_definition_graph(llm):
    builder = StateGraph(SystemDefinitionState)

    # =========================
    # Nodes
    # =========================

    builder.add_node(
        "REQUEST_SYSTEM_INPUT",
        log_node(
            "REQUEST_SYSTEM_INPUT",
            lambda s: request_system_input_node(s, llm),
        ),
    )

    builder.add_node(
        "INTERPRET_SYSTEM_INPUT",
        log_node(
            "INTERPRET_SYSTEM_INPUT",
            lambda s: interpret_system_input_node(s, llm),
        ),
    )

    builder.add_node(
        "REQUEST_FUNCTION_REFINEMENT",
        log_node(
            "REQUEST_FUNCTION_REFINEMENT",
            lambda s: request_refinement_node(s, llm),
        ),
    )

    builder.add_node(
        "UPDATE_SYSTEM_FUNCTIONS",
        log_node(
            "UPDATE_SYSTEM_FUNCTIONS",
            lambda s: update_system_functions_node(s, llm),
        ),
    )

    builder.add_edge(START, "REQUEST_SYSTEM_INPUT")

    builder.add_edge(START, "REQUEST_SYSTEM_INPUT")
    builder.add_edge("REQUEST_SYSTEM_INPUT", "INTERPRET_SYSTEM_INPUT")
    builder.add_edge("INTERPRET_SYSTEM_INPUT", "REQUEST_FUNCTION_REFINEMENT")

    builder.add_conditional_edges(
        "REQUEST_FUNCTION_REFINEMENT",
        lambda s: s["step"],
        {
            "UPDATE_SYSTEM_FUNCTIONS": "UPDATE_SYSTEM_FUNCTIONS",
            "FINAL": END,
        },
    )

    # =========================
    # Loop
    # =========================

    # update → refine again
    builder.add_edge("UPDATE_SYSTEM_FUNCTIONS", "REQUEST_FUNCTION_REFINEMENT")

    checkpointer = InMemorySaver()

    return builder.compile(checkpointer=checkpointer)
