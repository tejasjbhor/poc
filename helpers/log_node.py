import inspect


def log_node(name, fn):

    if inspect.iscoroutinefunction(fn):

        async def async_wrapper(state):
            print(f"[NODE START] {name}")
            result = await fn(state)
            print(f"[NODE END] {name}")
            return result

        return async_wrapper

    else:

        def sync_wrapper(state):
            print(f"[NODE START] {name}")
            result = fn(state)
            print(f"[NODE END] {name}")
            return result

        return sync_wrapper
