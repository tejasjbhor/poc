from langgraph.graph import StateGraph, START, END
from functools import partial

from helpers.log_node import log_node

from nodes.shared_nodes.context_definition_node import context_definition_node
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


def build_system_definition_graph(graph_name, llm):
    builder = StateGraph(SystemDefinitionState)

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
        "REQUEST_FUNCTION_REFINEMENT",
        log_node(
            graph_name,
            "REQUEST_FUNCTION_REFINEMENT",
            partial(request_refinement_node, llm=llm),
        ),
    )

    builder.add_node(
        "UPDATE_SYSTEM_FUNCTIONS",
        log_node(
            graph_name,
            "UPDATE_SYSTEM_FUNCTIONS",
            partial(update_system_functions_node, llm=llm),
        ),
    )

    builder.add_edge(START, "EXECUTION_CONTEXT_DEFINITION")
    builder.add_edge("EXECUTION_CONTEXT_DEFINITION", "REQUEST_SYSTEM_INPUT")
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
