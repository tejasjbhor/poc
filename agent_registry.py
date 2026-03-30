"""Agent registry: ids, node import paths, defaults."""

from __future__ import annotations

AGENTS: dict[str, dict] = {
    "agent_1": {
        "display_name": "agent_1",
        "node_fn": "agent_1.agent_1_node",
        "default_phase": "phase_1_needs",
        "runs_at_start": True,
        "description": "Structured requirements",
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


def get_node_fn(agent_id: str):
    import importlib
    entry = AGENTS.get(agent_id)
    if not entry:
        raise KeyError(f"Agent '{agent_id}' not in registry")

    module_path, fn_name = entry["node_fn"].rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, fn_name)


def get_default_agent_states() -> dict:
    states = {}
    for agent_id, cfg in AGENTS.items():
        states[agent_id] = {
            "status":      "active" if cfg.get("runs_at_start") else "idle",
            "phase":       cfg.get("default_phase", ""),
            "turn_count":  0,
            "covered":     [],
            "pending":     [],
            "last_output": None,
        }
    return states
