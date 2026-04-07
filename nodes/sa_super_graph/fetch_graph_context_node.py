from datetime import datetime, timezone

from helpers.ingress_context_from_main_graphs import build_graph_checkpoint_event_chain
from state.sa_super_graph import SaSuperGraphState


async def fetch_graph_context_node(state: SaSuperGraphState) -> dict:
    refs = state.get("graph_session_refs") or {}
    if not isinstance(refs, dict):
        refs = {}
    events = await build_graph_checkpoint_event_chain(refs)
    tick = {
        "kind": "sa_super_fetch",
        "at": datetime.now(timezone.utc).isoformat(),
        "refs_keys": list(refs.keys()),
    }
    return {"event_chain": [tick] + list(events)}
