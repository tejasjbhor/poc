"""Super-agent graph: user in, router picks agent, observer updates goals; then end (or card pause)."""

from __future__ import annotations

import logging
from typing import Any


from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent_registry import (
    get_all_agent_ids,
    get_default_active_agent_id,
    get_node_fn,
)
from nodes.sa_graph.sa_router_node import sa_router_node
from nodes.sa_graph.sa_user_input_node import sa_user_input_node
from nodes.sa_graph.sa_card_wait_node import sa_card_wait_node
from nodes.sa_graph.sa_observer_node import sa_observer_node
from state.sa_state import GraphState

logger = logging.getLogger(__name__)


def _route_after_sa_observer(state: GraphState) -> str:
    # Card from the observer means we stop and ask the user (see sa_card_wait node).
    
    if state.get("sa_card"):
        return "sa_card_wait"
    return END


def build_graph(checkpointer: Any | None = None) -> CompiledStateGraph:
    if checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()

    builder = StateGraph(GraphState)

    builder.add_node("user_input", sa_user_input_node)
    builder.add_node("sa_router", sa_router_node)
    builder.add_node("sa_observer", sa_observer_node)
    builder.add_node("sa_card_wait", sa_card_wait_node)

    all_agent_ids = get_all_agent_ids()
    
    for agent_id in all_agent_ids:
        node_fn = get_node_fn(agent_id)
        builder.add_node(agent_id, node_fn)
        logger.info("Graph: registered node '%s'", agent_id)

    builder.add_edge(START, "user_input")
    builder.add_edge("user_input", "sa_router")

    def _pick_agent(state: GraphState) -> str:
        aid = state.get("active_agent") or ""
        if aid in all_agent_ids:
            return aid
        d = get_default_active_agent_id()
        if d in all_agent_ids:
            return d
        return all_agent_ids[0] if all_agent_ids else ""

    path_map = {aid: aid for aid in all_agent_ids}
    builder.add_conditional_edges("sa_router", _pick_agent, path_map)

    for agent_id in all_agent_ids:
        builder.add_edge(agent_id, "sa_observer")

    # We used to always do: sa_observer -> END.

    # Now if there is a card we branch to sa_card_wait, then END.

    builder.add_conditional_edges(
        "sa_observer",
        _route_after_sa_observer,
        {
            "sa_card_wait": "sa_card_wait",
            END: END,
        },
    )
    builder.add_edge("sa_card_wait", END)

#==================
    graph = builder.compile(checkpointer=checkpointer)
    logger.info("Graph compiled. Checkpointer: %s", type(checkpointer).__name__)
    return graph
