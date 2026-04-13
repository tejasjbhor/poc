import json

from helpers.interpret_user_input import is_done_user_input
from langgraph.types import interrupt

from state.requirement_generation_graph import RequirementGenerationState


def _build_review_question(state: RequirementGenerationState) -> str:
    reqs = state.get("requirements") or []
    summary = json.dumps({"requirements": reqs}, indent=2, default=str)
    return (
        "Review the generated requirements below.\n"
        "Reply with done/ok/approve to finish, or describe changes to apply.\n\n"
        f"{summary}"
    )


def request_requirements_review_node(state: RequirementGenerationState, config):
    
    if not state.get("review_prompt"):
        review_prompt = _build_review_question(state)
    else:
        review_prompt = state["review_prompt"]

    raw = interrupt(
        {
            "question": review_prompt,
            "graph_name": config["configurable"]["graph_name"],
        }
    )

    feedback = raw.get("raw_user_input")
    feedback_str = feedback if isinstance(feedback, str) else str(feedback or "")

    if is_done_user_input(feedback_str):
        return {
            "review_prompt": review_prompt,
            "user_requirements_feedback": feedback_str,
            "step": "FINAL",
            "graph_name": config["configurable"]["graph_name"],
        }

    return {
        "review_prompt": review_prompt,
        "user_requirements_feedback": feedback_str,
        "step": "UPDATE_REQUIREMENTS",
        "graph_name": config["configurable"]["graph_name"],
    }
