"""Agent registry: ids, node import paths, defaults."""

from __future__ import annotations
import importlib


from registeries.graph_names import GRAPH_NAMES_REGISTERY
from registeries.internet_search_unified_tool_registery import INTERNET_SEARCH_TOOLS

AGENTS: dict[str, dict] = {
    "agent_1": {
        "display_name": "Agent 1",
        "node_fn": "nodes.sa_graph.agent_1_node.agent_1_node",
        "type": "node",
        "default_phase": "phase_1_needs",
        "runs_at_start": False,
        "description": "Structured requirements",
    },
    "system_definition": {
        "display_name": "layout_agent",
        "node_fn": "graphs.system_definition_graph.build_system_definition_graph",
        "type": "graph",
        "default_phase": "phase_layout",
        "runs_at_start": False,
        "description": "Getting system description and functions from user.",
    },
    "internet_search": {
        "display_name": "Internet Search Agent",
        "node_fn": "graphs.internet_search_graph.build_internet_search_graph",
        "type": "graph",
        "default_phase": "phase_layout",
        "runs_at_start": True,
        "description": "Searching the internet for a particular system.",
    },
    "layout": {
        "display_name": "Layout Agent",
        "node_fn": "graphs.layout_graph.build_facility_layout_graph",
        "type": "graph",
        "default_phase": "phase_layout",
        "runs_at_start": False,
        "description": "Generate a 2D layout for a given system.",
    },
}


def get_display_name(agent_id: str) -> str:
    entry = AGENTS.get(agent_id)
    if entry:
        return entry["display_name"]
    return agent_id.replace("_", " ").title()


def get_start_agents() -> list[str]:
    return [aid for aid, cfg in AGENTS.items() if cfg.get("runs_at_start")]


def get_all_agent_ids() -> list[str]:
    return list(AGENTS.keys())


def get_default_active_agent_id() -> str:
    starts = get_start_agents()
    if starts:
        return starts[0]
    ids = get_all_agent_ids()
    return ids[0] if ids else ""


def load_callable(path: str):
    module_path, fn_name = path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, fn_name)


def resolve_callable(agent_id: str, llm):
    entry = AGENTS[agent_id]
    fn = load_callable(entry["node_fn"])

    if entry.get("type") == "graph":
        # build once
        graph = fn(GRAPH_NAMES_REGISTERY[agent_id], llm)

        async def wrapper(state, config):
            last = None
            async for chunk in graph.astream(state, config=config):
                last = chunk
            return last

        return wrapper

    return fn


def get_default_agent_states() -> dict:
    states = {}
    for agent_id, cfg in AGENTS.items():
        states[agent_id] = {
            "status": "active" if cfg.get("runs_at_start") else "idle",
            "phase": cfg.get("default_phase", ""),
            "turn_count": 0,
            "covered": [],
            "pending": [],
            "last_output": None,
        }
    return states
