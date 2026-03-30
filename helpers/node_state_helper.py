from langgraph.types import Interrupt


def require(state, key, message, step):
    value = state.get(key)
    if not value:
        return None, {"__interrupt__": [Interrupt(value=message)], "last_step": step}
    return value, None
