from registeries.agent_registry import get_default_agent_states
from state.sa_state import PlatformState


async def sa_user_input_node(state: PlatformState) -> dict:
    import time

    messages = state.get("messages") or []
    last_human = next(
        (m for m in reversed(messages) if getattr(m, "type", "") == "human"),
        None,
    )

    new_event = {}
    if last_human:
        new_event = {
            "seq":     len(state.get("event_chain") or []) + 1,
            "agent":   "user",
            "type":    "input",
            "content": getattr(last_human, "content", ""),
            "ts":      time.time(),
        }

    agents = dict(state.get("agents") or {})
    if not agents:
        agents = get_default_agent_states()

    return {
        "agents":      agents,
        "event_chain": [new_event] if new_event else [],
    }