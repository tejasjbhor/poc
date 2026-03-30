from langgraph.graph import StateGraph, START, END

from helpers.log_node import log_node
from nodes.system_definition_graph.dispatch_user_input_node import dispatch_user_input_node
from nodes.system_definition_graph.conditional_routing_nodes import route_from_step
from nodes.system_definition_graph.finalize_system_definition_node import finalize_system_definition_node
from nodes.system_definition_graph.normalize_system_input_node import normalize_system_input_node
from nodes.system_definition_graph.request_refinement_node import request_refinement_node
from nodes.system_definition_graph.request_system_input_node import request_system_input_node
from nodes.system_definition_graph.interpret_system_input_node import interpret_system_input_node
from nodes.system_definition_graph.router_node import router_node
from nodes.system_definition_graph.update_system_functions_node import update_system_functions_node
from nodes.system_definition_graph.validate_system_functions_node import validate_system_functions_node
from state.system_definition_graph import SystemDefinitionState
from langgraph.checkpoint.memory import InMemorySaver


def build_system_definition_graph(llm):
    builder = StateGraph(SystemDefinitionState)

    # =========================
    # Nodes
    # =========================

    builder.add_node(
        "normalize",
        log_node("normalize", lambda s: normalize_system_input_node(s, llm)),
    )

    builder.add_node(
        "router",
        log_node("router", lambda s: router_node(s, llm)),
    )

    builder.add_node(
        "dispatch_input",
        log_node("dispatch_input", lambda s: dispatch_user_input_node(s)),
    )

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
        "VALIDATE_SYSTEM_FUNCTIONS",
        log_node(
            "VALIDATE_SYSTEM_FUNCTIONS",
            lambda s: validate_system_functions_node(s, llm),
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

    builder.add_node(
        "FINALIZE_SYSTEM_DEFINITION",
        log_node(
            "FINALIZE_SYSTEM_DEFINITION",
            lambda s: finalize_system_definition_node(s, llm),
        ),
    )

    # =========================
    # Flow
    # =========================

    builder.add_edge(START, "router")

    builder.add_conditional_edges(
        "router",
        route_from_step,
        {
            "REQUEST_SYSTEM_INPUT": "REQUEST_SYSTEM_INPUT",
            "INTERPRET_SYSTEM_INPUT": "INTERPRET_SYSTEM_INPUT",
            "VALIDATE_SYSTEM_FUNCTIONS": "VALIDATE_SYSTEM_FUNCTIONS",
            "REQUEST_FUNCTION_REFINEMENT": "REQUEST_FUNCTION_REFINEMENT",
            "UPDATE_SYSTEM_FUNCTIONS": "UPDATE_SYSTEM_FUNCTIONS",
            "FINALIZE_SYSTEM_DEFINITION": "FINALIZE_SYSTEM_DEFINITION",
        },
    )

    # =========================
    # User input → normalize → router
    # =========================

    for node in [
        "REQUEST_SYSTEM_INPUT",
        "REQUEST_FUNCTION_REFINEMENT",
    ]:
        builder.add_edge(node, "normalize")

    builder.add_edge("normalize", "router")

    # =========================
    # Processing nodes → router
    # =========================

    for node in [
        "INTERPRET_SYSTEM_INPUT",
        "VALIDATE_SYSTEM_FUNCTIONS",
        "UPDATE_SYSTEM_FUNCTIONS",
    ]:
        builder.add_edge(node, "router")

    # =========================
    # End
    # =========================

    builder.add_edge("FINALIZE_SYSTEM_DEFINITION", END)

    checkpointer = InMemorySaver()

    return builder.compile(checkpointer=checkpointer)
