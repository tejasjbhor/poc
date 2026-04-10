from __future__ import annotations

import importlib
from typing import Callable, Optional, Any

from registeries.graph_registery import GRAPH_NAMES_REGISTERY
from schemas.agents.agent_spec import AgentSpec


class AgentRuntime:
    def __init__(self, spec: AgentSpec):
        self.spec = spec
        self._fn: Optional[Callable] = None

    # -------------------------
    # Lazy loader
    # -------------------------
    def load_callable(self) -> Callable:
        if self._fn:
            return self._fn

        module_path, fn_name = self.spec.node_fn_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        self._fn = getattr(module, fn_name)
        return self._fn

    # -------------------------
    # Graph builder
    # -------------------------
    def build_graph(self, llm):
        fn = self.load_callable()
        graph_name = GRAPH_NAMES_REGISTERY[self.spec.agent_id]
        return fn(graph_name, llm)

    # -------------------------
    # Execution wrapper (LangGraph-compatible)
    # -------------------------
    def resolve(self, llm):

        # Non-graph agent (direct callable)
        if self.spec.type != "graph":
            return self.load_callable()

        async def wrapper(state, config):
            enriched_config = dict(config or {})
            enriched_config.setdefault("configurable", {})

            enriched_config["configurable"] = {
                **enriched_config["configurable"],
                "graph_name": GRAPH_NAMES_REGISTERY[self.spec.agent_id],
            }

            graph = self.build_graph(llm)
            return await graph.ainvoke(state, config=enriched_config)

        return wrapper

    def as_node(self, llm, graph_name, log_node_fn):
        node_fn = self.resolve(llm)

        async def wrapped(state, config):
            return await node_fn(state, config)

        return log_node_fn(
            graph_name,
            self.spec.agent_id,
            wrapped,
        )

    # -------------------------
    # Default state for orchestration
    # -------------------------
    def default_state(self) -> dict:
        return {
            "status": "active" if self.spec.runs_at_start else "idle",
            "phase": self.spec.default_phase,
            "turn_count": 0,
            "covered": [],
            "pending": [],
            "last_output": None,
        }
