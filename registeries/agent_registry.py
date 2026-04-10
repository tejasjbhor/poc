from __future__ import annotations

from typing import Dict, List

from langgraph.graph import END

from schemas.agents.agent_spec import AgentSpec
from domain.agents.agent_runtime import AgentRuntime


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, AgentRuntime] = {}

    # -------------------------
    # Register
    # -------------------------
    def register(self, spec: AgentSpec):
        self._agents[spec.agent_id] = AgentRuntime(spec)

    # -------------------------
    # Getters
    # -------------------------
    def get(self, agent_id: str) -> AgentRuntime:
        return self._agents[agent_id]

    def all(self) -> List[AgentRuntime]:
        return list(self._agents.values())

    def ids(self) -> List[str]:
        return list(self._agents.keys())

    def list_routes(self):
        return [
            {
                "id": agent.spec.agent_id.upper(),
                "description": agent.spec.description,
            }
            for agent in self._agents.values()
        ]

    def get_route_map(self):
        routes = {
            agent.spec.agent_id.upper(): agent.spec.agent_id.upper()
            for agent in self._agents.values()
        }

        routes["DECIDE_ROUTE"] = "DECIDE_ROUTE"
        routes["FINAL"] = END

        return routes

    def serialize_agents(registry):
        agents = []

        for a in registry.all():
            agents.append(
                {
                    "agent_id": a.agent_id,
                    "description": a.description,
                    "produces_data": list(a.produces_data),
                    "fixes_data": list(a.fixes_data),
                }
            )

        return agents

    # -------------------------
    # Discovery logic
    # -------------------------
    def start_agents(self) -> List[AgentRuntime]:
        return [a for a in self._agents.values() if a.spec.runs_at_start]

    def default_agent_id(self) -> str:
        starts = self.start_agents()
        if starts:
            return starts[0].spec.agent_id
        return next(iter(self._agents), "")

    # -------------------------
    # LangGraph integration
    # -------------------------
    def resolve(self, agent_id: str, llm):
        return self._agents[agent_id].resolve(llm)

    # -------------------------
    # State initialization
    # -------------------------
    def default_states(self) -> dict:
        return {
            agent_id: runtime.default_state()
            for agent_id, runtime in self._agents.items()
        }
