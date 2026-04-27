from datetime import datetime
from typing import Any, Dict

from helpers.ensure_execution_context import ensure_execution_context
from schemas.domain.context_definition_node import ExecutionContext


def execution_context_definition_node(
    state: ExecutionContext, config
) -> ExecutionContext:
    metadata: Dict[str, Any] = config.get("metadata") or {}  # safe access
    existing_ctx = ensure_execution_context(state.execution_context)
    # -------------------------
    # Identify current graph
    # -------------------------
    current_graph = config["configurable"]["graph_name"]
    # -------------------------
    # Run / tracing identity
    # -------------------------
    run_id = metadata.get("run_id") or existing_ctx.run_id

    # -------------------------
    # Parent graph detection (subgraph detection key)
    # -------------------------
    if (
        existing_ctx.current_graph is not None
        and current_graph != existing_ctx.current_graph
    ):
        parent_graph = existing_ctx.current_graph
        depth = existing_ctx.depth + 1
        previous_graph = existing_ctx.previous_graph or existing_ctx.current_graph
        source = "graph"
        mode = "subgraph"
    else:
        parent_graph = None
        source = "user"
        mode = "standalone"
        previous_graph = None
        depth = 0

    # -------------------------
    # Root graph resolution
    # -------------------------
    root_graph = existing_ctx.root_graph or parent_graph or current_graph

    # -------------------------
    # Build execution context
    # -------------------------
    execution_context: ExecutionContext = ExecutionContext(
        mode=mode,
        source=source,
        parent_graph=parent_graph,
        current_graph=current_graph,
        root_graph=root_graph,
        previous_graph=previous_graph,
        depth=depth,
        run_id=run_id,
    )

    # -------------------------
    # Return updated state
    # -------------------------
    return state.model_copy(
        update={
            "execution_context": execution_context,
            "graph_name": current_graph,
            "_emit": datetime.now(),
        }
    )
