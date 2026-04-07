"""
Workflow graphs on main_graph that sa_super_graph can observe (checkpoint pull).

"""

from __future__ import annotations

from typing import Any


def get_observable_graph_map() -> dict[str, Any]:
    from api import internet_search_ws as internet_search_mod
    from api import layout_ws as layout_mod
    from api import system_definition_ws as system_definition_mod

    return {
        "system_definition": system_definition_mod.graph,
        "layout": layout_mod.graph,
        "internet_search": internet_search_mod.graph,
    }


def get_observable_workflow_ids() -> list[str]:
    return list(get_observable_graph_map().keys())


def default_observable_workflow_id() -> str:
    ids = get_observable_workflow_ids()
    return ids[0] if ids else ""
