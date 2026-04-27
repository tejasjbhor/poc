from datetime import datetime
import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.ensure_execution_context import ensure_execution_context
from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.overall_observer import OVERALL_OBSERVER_PROMPTS
from registeries.agent_registry import AgentRegistry
from schemas.domain.context_definition_node import ExecutionContext
from schemas.domain.execution_stack import ExecutionTask
from state.overall_observer_graph import OverallObserverState
from utils.json_utils import coerce_json


def normalize_execution_context_node(
    state: OverallObserverState, config, llm
) -> OverallObserverState:
    existing_ctx = ensure_execution_context(state.execution_context)
    existing_execution_stack = state.execution_stack
    previous_graph = existing_ctx.current_graph
    # -------------------------
    # Identify current graph
    # -------------------------
    current_graph = config["configurable"]["graph_name"]
    # -------------------------
    # Run / tracing identity
    # -------------------------
    run_id = existing_ctx.run_id

    # -------------------------
    # Root graph resolution
    # -------------------------
    root_graph = existing_ctx.root_graph

    # -------------------------
    # CASE 1: New hydration request → PUSH
    # -------------------------
    if state.hydration_issues:
        agent_registry: AgentRegistry = (
            config.get("configurable").get("runtime").get("agent_registry")
        )
        agents = agent_registry.list_routes()

        prompt = OVERALL_OBSERVER_PROMPTS["pick_data_fixer_agent"]

        response = safe_llm_invoke(
            llm,
            [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=json.dumps(
                        {
                            "hydration_issues": state.hydration_issues,
                            "agents": agents,
                        }
                    )
                ),
            ],
        )

        routing = coerce_json(response.content)

        task = ExecutionTask(
            hydration_requester=state.hydration_requester,
            hydration_issues=state.hydration_issues,
            hydration_resolver=routing.get("agent_id"),
            reasoning=routing.get("reasoning"),
            status="pending",
        )

        existing_execution_stack.append(task)

    # -------------------------
    # CASE 2: Resolver finished → mark RETURNING
    # -------------------------
    elif existing_execution_stack:
        task = existing_execution_stack[-1]

        if task.status == "resolving":
            task.status = "returning"

        # -------------------------
        # CASE 3: Requester resumed → POP
        # -------------------------
        elif task.status == "returning":
            existing_execution_stack.pop()

    # -------------------------
    # Build execution context
    # -------------------------
    execution_context: ExecutionContext = ExecutionContext(
        mode="standalone",
        source="user",
        parent_graph=None,
        current_graph=current_graph,
        root_graph=root_graph,
        previous_graph=previous_graph,
        depth=0,
        run_id=run_id,
    )

    # -------------------------
    # Return updated state
    # -------------------------
    return {
        "execution_context": execution_context,
        "execution_stack": existing_execution_stack,
        "graph_name": current_graph,
        "hydration_requester": None,
        "hydration_issues": [],
        "_emit": datetime.now(),
    }
