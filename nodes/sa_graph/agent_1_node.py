"""Requirements elicitation agent (LangGraph node)."""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from services.llm.llm_config import ainvoke_with_retry, get_chat_model
from prompts.sa_prompts import AGENT1_SYSTEM
from state.sa_state import PlatformState

logger = logging.getLogger(__name__)

AGENT_ID = "agent_1"


def _build_system_prompt(state: PlatformState) -> str:
    base = AGENT1_SYSTEM
    sa_context = (state.get("sa_context_for_agent") or {}).get(AGENT_ID, "")
    if sa_context:
        return (
            base
            + "\n\n[Context from observer - use naturally:]\n"
            + sa_context
        )
    return base


def _current_agent_state(state: PlatformState) -> dict:
    return (state.get("agents") or {}).get(AGENT_ID, {})


def _updated_agents(state: PlatformState, patch: dict) -> dict:
    agents = dict(state.get("agents") or {})
    current = dict(agents.get(AGENT_ID) or {})
    current.update(patch)
    agents[AGENT_ID] = current
    return agents


async def agent_1_node(state: PlatformState) -> dict:
    logger.info("%s: node called", AGENT_ID)

    messages = state.get("messages") or []
    agent_state = _current_agent_state(state)
    turn_count = int(agent_state.get("turn_count") or 0)

    model = get_chat_model()
    system_prompt = _build_system_prompt(state)
    lc_messages = [SystemMessage(content=system_prompt)] + list(messages)
    chain = model | StrOutputParser()
    reply_text = await ainvoke_with_retry(chain, lc_messages)
    logger.info("%s: LLM replied (%d chars)", AGENT_ID, len(reply_text))

    ai_message = AIMessage(
        content=reply_text,
        additional_kwargs={"agent": AGENT_ID},
    )

    new_event: dict[str, Any] = {
        "seq":     len(state.get("event_chain") or []) + 1,
        "agent":   AGENT_ID,
        "type":    "output",
        "content": reply_text,
        "ts":      time.time(),
    }

    updated_agents = _updated_agents(state, {
        "status":      "active",
        "turn_count":  turn_count + 1,
        "last_output": reply_text,
        "phase":       agent_state.get("phase") or "phase_1_needs",
    })

    sa_context = dict(state.get("sa_context_for_agent") or {})
    sa_context.pop(AGENT_ID, None)

    return {
        "messages":             [ai_message],
        "active_agent":         AGENT_ID,
        "agents":               updated_agents,
        "event_chain":          [new_event],
        "sa_context_for_agent": sa_context,
    }
