from typing import Any, Dict, Literal

from state.shared_nodes_states.context_definition_node import ExecutionContext


def normalize_execution_context_node(
    state: ExecutionContext, config
) -> ExecutionContext:
    existing_ctx = state.get("execution_context") or {}
    previous_graph = state.get("execution_context").get("current_graph")
    # -------------------------
    # Identify current graph
    # -------------------------
    current_graph = config["configurable"]["graph_name"]
    # -------------------------
    # Run / tracing identity
    # -------------------------
    run_id = existing_ctx.get("run_id")

    # -------------------------
    # Root graph resolution
    # -------------------------
    root_graph = existing_ctx.get("root_graph")

    # -------------------------
    # Build execution context
    # -------------------------
    execution_context: ExecutionContext = {
        "mode": "standalone",
        "source": "user",
        "parent_graph": None,
        "current_graph": current_graph,
        "root_graph": root_graph,
        "previous_graph": previous_graph,
        "depth": 0,
        "run_id": run_id,
    }

    # -------------------------
    # Return updated state
    # -------------------------
    return {
        **state,
        "execution_context": execution_context,
        "graph_name": current_graph,
    }
