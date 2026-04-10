import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.overall_observer import OVERALL_OBSERVER_PROMPTS
from registeries.agent_registry import AgentRegistry
from langgraph.types import interrupt

from state.overall_observer_graph import OverallObserverState
from utils.json_utils import coerce_json


def manual_routing(
    state: OverallObserverState, llm, graph_name, registry: AgentRegistry
):
    prompt = OVERALL_OBSERVER_PROMPTS["generate_welcome_message"]

    agents = registry.list_routes()

    question = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(content=json.dumps({"agent_descriptions": agents})),
        ],
    ).content

    user_input = interrupt({"question": question, "graph_name": graph_name})

    raw = user_input["raw_user_input"].strip()

    next_step = None

    # numeric selection only (keep it simple)
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(agents):
            next_step = agents[idx]["id"]

    return state.model_copy(
        update={
            "last_step": state.step,
            "step": state.next_step,
            "next_step": next_step,
            "graph_name": graph_name,
        }
    )


def hydration_routing(state: OverallObserverState, llm, graph_name, registry: AgentRegistry):
    agents = registry.list_routes()

    prompt = OVERALL_OBSERVER_PROMPTS["pick_data_fixer_agent"]

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {"hydration_issues": state.hydration_issues, "agents": agents}
                )
            ),
        ],
    )

    routing = coerce_json(response.content)
    print("llm agent id", routing)
    return state.model_copy(
        update={
            "next_step": routing.get("agent_id"),
            "reasoning": routing.get("reasoning"),
            "last_step": state.step,
            "step": state.next_step,
            "graph_name": graph_name,
        }
    )
