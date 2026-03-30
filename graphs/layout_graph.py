from langgraph.graph import StateGraph, START, END

from helpers.log_node import log_node
from nodes.layout_graph.collect_process_list_node import collect_process_list_node
from nodes.layout_graph.dispatch_user_input_node import dispatch_user_input_node
from nodes.layout_graph.finalize_node import finalize_node
from nodes.layout_graph.ask_overall_surface_and_function_node import ask_overall_node
from nodes.layout_graph.collect_layout_constraints import collect_constraints_node
from nodes.layout_graph.conditional_routing_nodes import route_from_step
from nodes.layout_graph.generate_layout import generate_layout_node
from nodes.layout_graph.prepare_layout_summary import prepare_summary_node
from nodes.layout_graph.refine_layout import refine_layout_node
from nodes.layout_graph.request_layout_feedback import request_feedback_node
from nodes.layout_graph.validate_process_list import validate_process_list_node
from nodes.layout_graph.router_node import router_node
from nodes.layout_graph.normalize_user_input_node import normalize_user_input_node
from state.facility_layout_graph import FacilityState
from langgraph.checkpoint.memory import InMemorySaver


def build_graph(llm):
    builder = StateGraph(FacilityState)

    # Nodes
    builder.add_node(
        "normalize", log_node("normalize", lambda s: normalize_user_input_node(s, llm))
    )
    builder.add_node("router", log_node("router", lambda s: router_node(s, llm)))
    builder.add_node(
        "dispatch_input",
        log_node("dispatch_input", lambda s: dispatch_user_input_node(s)),
    )

    builder.add_node(
        "ASK_OVERALL_SURFACE_AND_FUNCTION",
        log_node(
            "ASK_OVERALL_SURFACE_AND_FUNCTION", lambda s: ask_overall_node(s, llm)
        ),
    )
    builder.add_node(
        "COLLECT_PROCESS_LIST",
        log_node("COLLECT_PROCESS_LIST", lambda s: collect_process_list_node(s, llm)),
    )
    builder.add_node(
        "VALIDATE_PROCESS_LIST",
        log_node("VALIDATE_PROCESS_LIST", lambda s: validate_process_list_node(s, llm)),
    )
    builder.add_node(
        "COLLECT_LAYOUT_CONSTRAINTS",
        log_node(
            "COLLECT_LAYOUT_CONSTRAINTS", lambda s: collect_constraints_node(s, llm)
        ),
    )
    builder.add_node(
        "PREPARE_LAYOUT_SUMMARY",
        log_node("PREPARE_LAYOUT_SUMMARY", lambda s: prepare_summary_node(s, llm)),
    )
    builder.add_node(
        "GENERATE_LAYOUT",
        log_node("GENERATE_LAYOUT", lambda s: generate_layout_node(s, llm)),
    )
    builder.add_node(
        "REQUEST_LAYOUT_FEEDBACK",
        log_node("REQUEST_LAYOUT_FEEDBACK", lambda s: request_feedback_node(s, llm)),
    )
    builder.add_node(
        "REFINE_LAYOUT", log_node("REFINE_LAYOUT", lambda s: refine_layout_node(s, llm))
    )
    builder.add_node(
        "FINALIZE_APPROVED_LAYOUT",
        log_node("FINALIZE_APPROVED_LAYOUT", lambda s: finalize_node(s, llm)),
    )

    # Flow
    builder.add_edge(START, "router")

    builder.add_conditional_edges(
        "router",
        route_from_step,
        {
            "ASK_OVERALL_SURFACE_AND_FUNCTION": "ASK_OVERALL_SURFACE_AND_FUNCTION",
            "COLLECT_PROCESS_LIST": "COLLECT_PROCESS_LIST",
            "VALIDATE_PROCESS_LIST": "VALIDATE_PROCESS_LIST",
            "COLLECT_LAYOUT_CONSTRAINTS": "COLLECT_LAYOUT_CONSTRAINTS",
            "PREPARE_LAYOUT_SUMMARY": "PREPARE_LAYOUT_SUMMARY",
            "GENERATE_LAYOUT": "GENERATE_LAYOUT",
            "REQUEST_LAYOUT_FEEDBACK": "REQUEST_LAYOUT_FEEDBACK",
            "REFINE_LAYOUT": "REFINE_LAYOUT",
            "FINALIZE_APPROVED_LAYOUT": "FINALIZE_APPROVED_LAYOUT",
        },
    )

    # After user input → normalize → router again
    for node in [
        "ASK_OVERALL_SURFACE_AND_FUNCTION",
        "COLLECT_PROCESS_LIST",
        "COLLECT_LAYOUT_CONSTRAINTS",
        "REQUEST_LAYOUT_FEEDBACK",
    ]:
        builder.add_edge(node, "normalize")

    builder.add_edge("normalize", "router")

    # Processing nodes → back to router
    for node in [
        "VALIDATE_PROCESS_LIST",
        "PREPARE_LAYOUT_SUMMARY",
        "GENERATE_LAYOUT",
        "REFINE_LAYOUT",
    ]:
        builder.add_edge(node, "router")

    builder.add_edge("FINALIZE_APPROVED_LAYOUT", END)

    checkpointer = InMemorySaver()

    return builder.compile(checkpointer=checkpointer)
