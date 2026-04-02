import inspect


def log_node(graph_name, name, fn):

    if inspect.iscoroutinefunction(fn):

        async def async_wrapper(state):
            print(f"[NODE START] {graph_name}/{name}")
            result = await fn(state)
            print(f"[NODE END] {graph_name}/{name}")
            return result

        return async_wrapper

    else:

        def sync_wrapper(state):
            print(f"[NODE START] {graph_name}/{name}")
            result = fn(state)
            print(f"[NODE END] {graph_name}/{name}")
            return result

        return sync_wrapper
