"""Agent registry: ids, node import paths, defaults."""

from __future__ import annotations
import importlib


from registeries.graph_registery import GRAPH_NAMES_REGISTERY

AGENTS: dict[str, dict] = {
    "system_definition": {
        "display_name": "System Definition",
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
        "runs_at_start": False,
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

        async def wrapper(state, config):
            enriched_config = dict(config or {})
            enriched_config.setdefault("configurable", {})
            enriched_config["configurable"] = {
                **enriched_config["configurable"],
                "graph_name": GRAPH_NAMES_REGISTERY[agent_id],
            }

            # build once
            graph = fn(GRAPH_NAMES_REGISTERY[agent_id], llm)

            result = await graph.ainvoke(state, config=enriched_config)
            return result

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
