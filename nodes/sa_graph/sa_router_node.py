from agent_registry import get_all_agent_ids, get_default_active_agent_id
from state.sa_state import PlatformState
import structlog

log = structlog.get_logger(__name__)

async def sa_router_node(state: PlatformState) -> dict:
    all_ids = set(get_all_agent_ids())
    default = get_default_active_agent_id()

    na = (state.get("next_agent") or "").strip()
    if na in all_ids:
        chosen = na
    else:
        cur = (state.get("active_agent") or "").strip()
        chosen = cur if cur in all_ids else default

    log.info("sa_router: active_agent=%s", chosen)
    return {"active_agent": chosen}