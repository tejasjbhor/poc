"""Waits for the user to answer the Super Agent card (proceed / decline / skip)."""

from __future__ import annotations

from langgraph.types import interrupt

from prompts.sa_prompts import SA_CARD_INTERRUPT_KIND
from state.sa_state import PlatformState


def _normalize_card_resume(resume_val: object) -> str:
    if isinstance(resume_val, dict):
        v = resume_val.get("action") or resume_val.get("value") or ""
        return str(v).strip().lower()
    return str(resume_val).strip().lower()


async def sa_card_wait_node(state: PlatformState) -> dict:
    card = state.get("sa_card")
    if not card:
        return {}

    # Pause here. The CLI or API sends the answer on the next line; graph continues with that text.
    resume_val = interrupt(
        {
            "kind": SA_CARD_INTERRUPT_KIND,
            "title": card.get("title", ""),
            "body": card.get("body", ""),
            "suggestion_id": card.get("suggestion_id"),
        }
    )

    text = _normalize_card_resume(resume_val)

    if text in ("proceed", "p"):
        return {"sa_feedback": "proceed", "sa_card": None}
    if text in ("decline", "d"):
        return {"sa_feedback": "decline", "sa_card": None}
    # Enter or anything else: drop the card, no proceed/decline flag
    return {"sa_card": None}
