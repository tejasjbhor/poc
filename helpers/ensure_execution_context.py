from state.shared_nodes_states.context_definition_node import ExecutionContext


def ensure_execution_context(ctx):
    if isinstance(ctx, ExecutionContext):
        return ctx

    return ExecutionContext(**(ctx or {}))
