"""SA observer node: runs after the active agent; sets next_agent and SA fields."""

from __future__ import annotations

import json
import structlog

import re
import uuid

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from registeries.agent_registry import get_all_agent_ids, get_default_active_agent_id
from llm_config import ainvoke_with_retry, get_chat_model
from prompts.sa_prompts import SA_SYSTEM
from state.sa_state import BufferItem, PlatformState

logger = structlog.get_logger(__name__)


def _build_sa_input(state: PlatformState) -> dict:
    agents_raw = state.get("agents") or {}
    agents_clean = {}
    for agent_id, agent_state in agents_raw.items():
        agents_clean[agent_id] = {
            "status":     agent_state.get("status", "idle"),
            "turn_count": agent_state.get("turn_count", 0),
            "covered":    agent_state.get("covered", []),
            "pending":    agent_state.get("pending", []),
        }

    return {
        "active_agent":        state.get("active_agent") or get_default_active_agent_id(),
        "registered_agents":   get_all_agent_ids(),
        "agents":              agents_clean,
        "events":              state.get("event_chain") or [],
        "prior_session_goal":  state.get("session_goal") or "",
        "prior_goal_progress": state.get("goal_progress") or "",
        "prior_patterns":      [],
    }


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```\s*$", "", raw)
    return json.loads(raw)


def _normalise(data: dict) -> dict:
    thoughts = data.get("live_thinking") or data.get("thoughts") or []
    if not isinstance(thoughts, list):
        thoughts = [str(thoughts)]
    thoughts = [str(t) for t in thoughts if t]

    checklist: list[dict] = []
    for item in (data.get("checklist") or []):
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
            "title":              str(data["card_title"]).strip(),
            "body":               str(data.get("card_body") or "").strip(),
            "recommended_action": str(ra).strip() if ra else None,
            "suggestion_id":      str(uuid.uuid4()),
        }

    raw_instructions = data.get("pending_instructions") or []
    instructions: list[dict] = []
    for inst in raw_instructions:
        if isinstance(inst, dict) and inst.get("for_agent") and inst.get("content"):
            instructions.append({
                "id":        str(uuid.uuid4()),
                "for_agent": str(inst["for_agent"]),
                "content":   str(inst["content"]),
                "fired":     False,
            })

    allowed = set(get_all_agent_ids())
    raw_next = str(data.get("next_agent") or "").strip()
    next_agent = raw_next if raw_next in allowed else ""

    return {
        "inferred_domain": str(data.get("inferred_domain") or "").strip(),
        "inferred_task":   str(data.get("inferred_task_type") or "").strip(),
        "phase":           str(data.get("phase") or "").strip(),
        "session_goal":    str(data.get("session_goal") or "").strip(),
        "goal_progress":   str(data.get("goal_progress") or "").strip(),
        "next_agent":      next_agent,
        "thoughts":        thoughts,
        "checklist":       checklist,
        "card":            card,
        "instructions":    instructions,
    }


def _process_buffer(
    state: PlatformState,
    new_items: list[dict],
) -> tuple[list[BufferItem], dict[str, str]]:
    active_agent = state.get("active_agent") or ""
    existing = list(state.get("sa_readiness_buffer") or [])

    existing_contents = {item.get("content") for item in existing}
    for item in new_items:
        if item.get("content") not in existing_contents:
            existing.append(item)

    context_map: dict[str, str] = dict(state.get("sa_context_for_agent") or {})

    updated_buffer: list[BufferItem] = []
    for item in existing:
        if item.get("fired"):
            updated_buffer.append(item)
            continue

        target = item.get("for_agent", "")
        if target == active_agent:
            item = dict(item)
            item["fired"] = True
            logger.info(
                "SA buffer: firing item for %s - %s",
                target,
                item.get("content", "")[:60],
            )
            existing_ctx = context_map.get(target, "")
            sep = "\n" if existing_ctx else ""
            context_map[target] = existing_ctx + sep + item["content"]

        updated_buffer.append(item)

    return updated_buffer, context_map


async def sa_observer_node(state: PlatformState) -> dict:
    logger.info("sa_observer: node called")

    messages = state.get("messages") or []
    if not messages:
        logger.debug("sa_observer: no messages, skip")
        return {}

    sa_input = _build_sa_input(state)

    model = get_chat_model()
    payload_str = json.dumps(sa_input, ensure_ascii=False, indent=2)

    lc_messages = [
        SystemMessage(content=SA_SYSTEM),
        HumanMessage(content="State:\n\n" + payload_str),
    ]
    chain = model | StrOutputParser()
    raw = await ainvoke_with_retry(chain, lc_messages)
    result = _normalise(_parse_json(raw))

    fallback = get_default_active_agent_id()
    cur_active = (state.get("active_agent") or "").strip() or fallback
    all_ids = get_all_agent_ids()
    next_agent = (result["next_agent"] or cur_active).strip()
    if next_agent not in all_ids:
        next_agent = (
            cur_active
            if cur_active in all_ids
            else (fallback if fallback in all_ids else (all_ids[0] if all_ids else ""))
        )

    logger.info(
        "sa_observer: domain='%s' next_agent=%s card=%s",
        result["inferred_domain"],
        next_agent,
        result["card"] is not None,
    )

    updated_buffer, context_map = _process_buffer(state, result.get("instructions") or [])

    return {
        "sa_inferred_domain":   result["inferred_domain"],
        "sa_inferred_task":     result["inferred_task"],
        "sa_phase":             result["phase"],
        "sa_thoughts":          result["thoughts"],
        "sa_checklist":         result["checklist"],
        "sa_card":              result["card"],
        "sa_readiness_buffer":  updated_buffer,
        "sa_context_for_agent": context_map,
        "sa_feedback":          None,
        "next_agent":           next_agent,
        "session_goal":         result["session_goal"] or (state.get("session_goal") or ""),
        "goal_progress":        result["goal_progress"] or (state.get("goal_progress") or ""),
    }


super_agent_node = sa_observer_node
