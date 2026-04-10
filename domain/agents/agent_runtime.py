from __future__ import annotations

import importlib
from typing import Callable, Optional, Any

from api import ws_manager_graph
from registeries.graph_registery import GRAPH_NAMES_REGISTERY
from schemas.agents.agent_spec import AgentSpec
from utils.execution_events import begin_graph_execution, build_graph_execution_message


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

        # -------------------------
        # Non-graph agent
        # -------------------------
        if self.spec.type != "graph":
            return self.load_callable()

        # -------------------------
        # Graph agent
        # -------------------------
        async def wrapper(state, config):
            enriched_config = dict(config or {})
            enriched_config.setdefault("configurable", {})

            configurable = enriched_config["configurable"]
            session_id = configurable.get("thread_id")

            graph_name = GRAPH_NAMES_REGISTERY[self.spec.agent_id]

            enriched_config["configurable"] = {
                **configurable,
                "graph_name": graph_name,
            }

            # -------------------------
            # Build execution metadata
            # -------------------------
            graph_execution = begin_graph_execution(
                graph_name,
                session_id,
                trigger="subgraph",
            )

            # -------------------------
            # Broadcast START
            # -------------------------
            if session_id:
                await ws_manager_graph.send(
                    session_id,
                    build_graph_execution_message(
                        graph_execution,
                        status="started",
                        extra={"entrypoint_node": self.spec.agent_id.upper()},
                    ),
                )

            try:
                # -------------------------
                # Build graph (cache it)
                # -------------------------
                if not hasattr(self, "_graph") or self._graph is None:
                    self._graph = self.build_graph(llm)

                result = await self._graph.ainvoke(state, config=enriched_config)

            except Exception as error:
                # -------------------------
                # Handle failure / pause
                # -------------------------
                if session_id:
                    status = (
                        "paused"
                        if error.__class__.__name__ == "GraphInterrupt"
                        else "failed"
                    )

                    await ws_manager_graph.send(
                        session_id,
                        build_graph_execution_message(
                            graph_execution,
                            status=status,
                            error=error,
                            extra={"entrypoint_node": self.spec.agent_id.upper()},
                        ),
                    )

                raise

            except BaseException as error:
                # -------------------------
                # Handle special interrupts
                # -------------------------
                if session_id and error.__class__.__name__ == "GraphInterrupt":
                    await ws_manager_graph.send(
                        session_id,
                        build_graph_execution_message(
                            graph_execution,
                            status="paused",
                            error=error,
                            extra={"entrypoint_node": self.spec.agent_id.upper()},
                        ),
                    )

                raise

            else:
                # -------------------------
                # Broadcast SUCCESS
                # -------------------------
                if session_id:
                    await ws_manager_graph.send(
                        session_id,
                        build_graph_execution_message(
                            graph_execution,
                            status="completed",
                            result=result,
                            extra={"entrypoint_node": self.spec.agent_id.upper()},
                        ),
                    )

                return result

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
