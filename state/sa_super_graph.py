from typing import Annotated, Any, List, Optional, TypedDict


def _append_events(existing: list, update: list) -> list:
    return list(existing or []) + list(update or [])


class SaSuperGraphState(TypedDict, total=False):
    step: str
    graph_session_refs: dict[str, Any]
    ingress_context: dict[str, Any]
    active_agent: str
    event_chain: Annotated[list, _append_events]

    sa_inferred_domain: str
    sa_inferred_task: str
    sa_phase: str
    session_goal: str
    goal_progress: str
    next_agent: str
    sa_thoughts: list[str]
    sa_checklist: list[dict[str, Any]]
    sa_card: dict[str, Any] | None
    sa_readiness_buffer: list[dict[str, Any]]
    sa_context_for_workflow: dict[str, str]
