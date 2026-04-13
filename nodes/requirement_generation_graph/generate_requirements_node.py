from __future__ import annotations

import json
from typing import Optional

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.requirement_generation_prompts import REQUIREMENT_GENERATION_PROMPTS
from state.requirement_generation_graph import RequirementGenerationState
from utils.json_utils import coerce_json


def _selected_function(state: RequirementGenerationState) -> Optional[dict]:
    fid = state.get("selected_function_id")
    if not fid:
        return None
    for f in state.get("system_functions") or []:
        if isinstance(f, dict) and f.get("id") == fid:
            return f
    return None


def generate_requirements_node(state: RequirementGenerationState, config, llm):
    fn = _selected_function(state)
    if not fn:
        raise ValueError("selected_function_id must reference a system function")

    system = REQUIREMENT_GENERATION_PROMPTS["prompt_generate_requirements"]
    payload = {
        "system_description": state.get("system_description"),
        "selected_function": fn,
        "assumptions": state.get("assumptions") or [],
    }

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=system),
            HumanMessage(content=json.dumps(payload)),
        ],
    )

    try:
        parsed = coerce_json(response.content)
    except Exception:
        parsed = {}

    requirements = parsed.get("requirements") or []

    return {
        "requirements": requirements,
        "graph_name": config["configurable"]["graph_name"],
    }
