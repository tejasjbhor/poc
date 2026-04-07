import json

from langchain_core.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from helpers.sa_super_graph_llm import (
    build_sa_super_input,
    get_sa_system_prompt,
    normalise_observer_output,
    parse_observer_json,
    process_instruction_buffer,
)
from registeries.observable_workflows import (
    default_observable_workflow_id,
    get_observable_workflow_ids,
)
from state.sa_super_graph import SaSuperGraphState


def super_observer_llm_node(state: SaSuperGraphState, llm) -> dict:
    sa_input = build_sa_super_input(state)
    payload_str = json.dumps(sa_input, ensure_ascii=False, default=str)
    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=get_sa_system_prompt()),
            HumanMessage(content="State:\n\n" + payload_str),
        ],
    )
    text = (getattr(response, "content", None) or "").strip()
    result = normalise_observer_output(parse_observer_json(text))

    allowed = set(get_observable_workflow_ids())
    fallback = default_observable_workflow_id()
    cur_active = (state.get("active_agent") or "").strip() or fallback
    if cur_active not in allowed:
        cur_active = fallback
    next_agent = (result["next_agent"] or cur_active).strip()
    if next_agent not in allowed:
        next_agent = cur_active

    merged = {**dict(state), "next_agent": next_agent}
    buf, ctx_map = process_instruction_buffer(
        merged,
        result.get("instructions") or [],
    )

    return {
        "sa_inferred_domain": result["inferred_domain"],
        "sa_inferred_task": result["inferred_task"],
        "sa_phase": result["phase"],
        "session_goal": result["session_goal"] or (state.get("session_goal") or ""),
        "goal_progress": result["goal_progress"] or (state.get("goal_progress") or ""),
        "next_agent": next_agent,
        "sa_thoughts": result["thoughts"],
        "sa_checklist": result["checklist"],
        "sa_card": result["card"],
        "sa_readiness_buffer": buf,
        "sa_context_for_workflow": ctx_map,
        "step": "FINAL",
    }
