from typing import Any, Dict, Literal

from state.shared_nodes_states.context_definition_node import ExecutionContext


def context_definition_node(state: ExecutionContext, config) -> ExecutionContext:
    metadata: Dict[str, Any] = config.get("metadata") or {}  # safe access
    existing_ctx = state.get("execution_context") or {}
    # -------------------------
    # Identify current graph
    # -------------------------
    current_graph = config["configurable"]["graph_name"]
    # -------------------------
    # Run / tracing identity
    # -------------------------
    run_id = metadata.get("run_id") or state.get("run_id")

    # -------------------------
    # Parent graph detection (subgraph detection key)
    # -------------------------
    if "current_graph" in existing_ctx and current_graph != existing_ctx.get(
        "current_graph"
    ):
        parent_graph = existing_ctx.get("current_graph")
        depth = existing_ctx.get("depth") + 1
        source = "graph"
        mode: Literal["standalone", "subgraph", "resume", "batch"] = "subgraph"
    else:
        parent_graph = None
        source = "user"
        mode = "standalone"
        depth = 0

    # -------------------------
    # Root graph resolution
    # -------------------------
    root_graph = existing_ctx.get("root_graph") or parent_graph or current_graph

    # -------------------------
    # Build execution context
    # -------------------------
    execution_context: ExecutionContext = {
        "mode": mode,
        "source": source,
        "parent_graph": parent_graph,
        "current_graph": current_graph,
        "root_graph": root_graph,
        "depth": depth,
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
