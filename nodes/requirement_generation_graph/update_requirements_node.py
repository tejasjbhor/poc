import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.requirement_generation_prompts import REQUIREMENT_GENERATION_PROMPTS
from state.requirement_generation_graph import RequirementGenerationState
from utils.json_utils import coerce_json


def update_requirements_node(state: RequirementGenerationState, config, llm):
    prompt = REQUIREMENT_GENERATION_PROMPTS["prompt_update_requirements"]
    payload = {
        "requirements": state.get("requirements") or [],
        "user_feedback": state.get("user_requirements_feedback") or "",
    }

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(content=json.dumps(payload, default=str)),
        ],
    )

    try:
        parsed = coerce_json(response.content)
    except Exception:
        parsed = {}

    requirements = parsed.get("requirements")
    if not isinstance(requirements, list):
        requirements = state.get("requirements") or []

    return {
        "requirements": requirements,
        "review_prompt": None,
        "graph_name": config["configurable"]["graph_name"],
    }
