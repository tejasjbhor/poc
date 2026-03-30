from langchain.messages import HumanMessage, SystemMessage
import structlog

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState

logger = structlog.get_logger(__name__)


from langchain.messages import HumanMessage, SystemMessage
import structlog

logger = structlog.get_logger(__name__)


def route_from_step(state: SystemDefinitionState):
    return state.get("last_step") or "REQUEST_SYSTEM_INPUT"


def router_node(state: SystemDefinitionState, llm):

    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_detect_next_workflow_step"]

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Current state: {state}"),
        ],
    )

    full_text = getattr(response, "text", None) or response[0].content
    next_step = full_text.strip().splitlines()[-1].strip()

    if not next_step:
        next_step = route_from_step(state)

    print(f"➡️ TRANSITION: {state.get('last_step')} → {next_step}")

    # ✅ UPDATED INTERRUPT LOGIC
    if next_step in [
        "REQUEST_SYSTEM_INPUT",
        "REQUEST_FUNCTION_REFINEMENT",
    ]:
        return {"last_step": next_step}

    return {"last_step": next_step}
