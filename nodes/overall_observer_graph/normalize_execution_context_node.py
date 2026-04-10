from helpers.ensure_execution_context import ensure_execution_context
from schemas.domain.context_definition_node import ExecutionContext


def normalize_execution_context_node(
    state: ExecutionContext, config
) -> ExecutionContext:
    existing_ctx = ensure_execution_context(state.execution_context)
    previous_graph = existing_ctx.current_graph
    # -------------------------
    # Identify current graph
    # -------------------------
    current_graph = config["configurable"]["graph_name"]
    # -------------------------
    # Run / tracing identity
    # -------------------------
    run_id = existing_ctx.run_id

    # -------------------------
    # Root graph resolution
    # -------------------------
    root_graph = existing_ctx.root_graph

    # -------------------------
    # Build execution context
    # -------------------------
    execution_context: ExecutionContext = ExecutionContext(
        mode="standalone",
        source="user",
        parent_graph=None,
        current_graph=current_graph,
        root_graph=root_graph,
        previous_graph=previous_graph,
        depth=0,
        run_id=run_id,
    )

    # -------------------------
    # Return updated state
    # -------------------------
    return state.model_copy(
        update={
            "execution_context": execution_context,
            "graph_name": current_graph,
        }
    )
