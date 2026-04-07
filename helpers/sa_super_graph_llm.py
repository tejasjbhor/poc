from __future__ import annotations

import json
import re
import uuid
from typing import Any

from prompts.sa_prompts import SA_SYSTEM
from registeries.observable_workflows import (
    default_observable_workflow_id,
    get_observable_workflow_ids,
)


def _workflow_ids() -> list[str]:
    return get_observable_workflow_ids()


def _workflow_id_set() -> set[str]:
    return set(_workflow_ids())


def _default_agent_slot() -> dict[str, Any]:
    return {
        "status": "idle",
        "turn_count": 0,
        "covered": [],
        "pending": [],
    }


def build_workflow_summaries_from_event_chain(chain: list[Any]) -> dict[str, dict[str, Any]]:
    ids = _workflow_ids()
    out = {g: _default_agent_slot() for g in ids}
    seen: set[str] = set()
    for ev in reversed(chain or []):
        if not isinstance(ev, dict):
            continue
        if ev.get("kind") == "sa_super_fetch":
            continue
        if ev.get("kind") != "graph_checkpoint":
            continue
        g = ev.get("graph")
        if g not in out or g in seen:
            continue
        seen.add(g)
        if ev.get("skipped"):
            out[g] = {
                "status": "idle",
                "turn_count": 0,
                "covered": ["skipped"],
                "pending": [],
            }
            continue
        st = ev.get("state")
        if not isinstance(st, dict) or not st:
            out[g] = {
                "status": "idle",
                "turn_count": 0,
                "covered": ["no_checkpoint"],
                "pending": [],
            }
            continue
        step = str(st.get("step") or "")
        out[g] = {
            "status": "active",
            "turn_count": 1,
            "covered": [f"step={step}"] if step else ["has_state"],
            "pending": [],
        }
    return out


def build_sa_super_input(state: dict[str, Any]) -> dict[str, Any]:
    chain = list(state.get("event_chain") or [])
    agents = build_workflow_summaries_from_event_chain(chain)
    ids = _workflow_ids()
    active = (state.get("active_agent") or "").strip()
    if active not in _workflow_id_set():
        active = default_observable_workflow_id()
    ingress = state.get("ingress_context") or {}
    payload: dict[str, Any] = {
        "active_agent": active,
        "registered_agents": list(ids),
        "agents": agents,
        "events": chain[-48:],
        "prior_session_goal": state.get("session_goal") or "",
        "prior_goal_progress": state.get("goal_progress") or "",
        "prior_patterns": [],
    }
    if isinstance(ingress, dict) and ingress:
        payload["client_ingress_context"] = ingress
    return payload


def parse_observer_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```\s*$", "", raw)
    return json.loads(raw)


def normalise_observer_output(data: dict[str, Any]) -> dict[str, Any]:
    thoughts_raw = data.get("live_thinking") or data.get("thoughts") or []
    if not isinstance(thoughts_raw, list):
        thoughts_raw = [str(thoughts_raw)]
    thoughts = [str(t) for t in thoughts_raw if t]

    checklist: list[dict[str, Any]] = []
    for item in data.get("checklist") or []:
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            status = str(item.get("status") or "missing").lower()
            if status not in ("defined", "partial", "missing"):
                status = "missing"
            if label:
                checklist.append({"label": label, "status": status})

    card = None
    if data.get("show_card") and data.get("card_title"):
        ra = data.get("recommended_action")
        card = {
            "title": str(data["card_title"]).strip(),
            "body": str(data.get("card_body") or "").strip(),
            "recommended_action": str(ra).strip() if ra else None,
            "suggestion_id": str(uuid.uuid4()),
        }

    allowed = _workflow_id_set()
    raw_instructions = data.get("pending_instructions") or []
    instructions: list[dict[str, Any]] = []
    for inst in raw_instructions:
        if isinstance(inst, dict) and inst.get("for_agent") and inst.get("content"):
            aid = str(inst["for_agent"])
            if aid not in allowed:
                continue
            instructions.append({
                "id": str(uuid.uuid4()),
                "for_agent": aid,
                "content": str(inst["content"]),
                "fired": False,
            })

    raw_next = str(data.get("next_agent") or "").strip()
    next_agent = raw_next if raw_next in allowed else ""

    return {
        "inferred_domain": str(data.get("inferred_domain") or "").strip(),
        "inferred_task": str(data.get("inferred_task_type") or "").strip(),
        "phase": str(data.get("phase") or "").strip(),
        "session_goal": str(data.get("session_goal") or "").strip(),
        "goal_progress": str(data.get("goal_progress") or "").strip(),
        "next_agent": next_agent,
        "thoughts": thoughts,
        "checklist": checklist,
        "card": card,
        "instructions": instructions,
    }


def get_sa_system_prompt() -> str:
    return SA_SYSTEM


def process_instruction_buffer(
    state: dict[str, Any],
    new_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    allowed = _workflow_id_set()
    active = (state.get("next_agent") or state.get("active_agent") or "").strip()
    if active not in allowed:
        active = default_observable_workflow_id()
    existing = list(state.get("sa_readiness_buffer") or [])
    existing_contents = {item.get("content") for item in existing}
    for item in new_items:
        if item.get("content") not in existing_contents:
            existing.append(item)

    context_map: dict[str, str] = dict(state.get("sa_context_for_workflow") or {})
    updated_buffer: list[dict[str, Any]] = []
    for item in existing:
        if item.get("fired"):
            updated_buffer.append(item)
            continue
        target = str(item.get("for_agent", ""))
        if target == active:
            item = dict(item)
            item["fired"] = True
            existing_ctx = context_map.get(target, "")
            sep = "\n" if existing_ctx else ""
            context_map[target] = existing_ctx + sep + str(item.get("content", ""))
        updated_buffer.append(item)
    return updated_buffer, context_map
