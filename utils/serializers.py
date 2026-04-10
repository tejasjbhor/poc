from datetime import datetime, timezone

from api.ws_manager_graph import ws_manager_graph
from helpers.interrupt_normalizer import normalize_interrupts
from registeries.graph_ws_serializers import GRAPH_WS_SERIALIZERS
from schemas.graphs.internet_search.output import InternetSearchOutput
from schemas.graphs.layout.output import LayoutOutput
from schemas.graphs.system_definition.output import SystemDefinitionOutput


def normalize_graph_event(update, seen_interrupt_ids=None):
    if not update:
        return None

    if "__interrupt__" in update:
        return normalize_interrupts(update["__interrupt__"], seen_interrupt_ids)

    # 2. Normal node output
    node_name, payload = next(iter(update.items()))
    # =========================
    # GRAPH-SPECIFIC ROUTING
    # =========================
    handler = GRAPH_WS_SERIALIZERS.get(payload.get("graph_name"))
    if handler:
        return handler(node_name, payload)


async def normalize_finished_event(session_id, state):
    graph_name = state.get("execution_context").get("current_graph")

    if graph_name == "system_definition":
        system_definition: SystemDefinitionOutput = state.get("system_definition")
        return await ws_manager_graph.send(
            session_id,
            {
                "type": "finished",
                "graph_name": graph_name,
                "data": {
                    "system_description": system_definition.get("system_description"),
                    "system_functions": system_definition.get("system_functions"),
                    "assumptions": system_definition.get("assumptions"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    if graph_name == "layout":
        system_definition: SystemDefinitionOutput = state.get("system_definition")
        final_layout: LayoutOutput = state.get("final_layout")
        return await ws_manager_graph.send(
            session_id,
            {
                "type": "finished",
                "graph_name": graph_name,
                "data": {
                    "system_description": system_definition.get(
                        "system_description", ""
                    ),
                    "system_functions": system_definition.get("system_functions", []),
                    "assumptions": system_definition.get("assumptions", {}),
                    "constraints": final_layout.get("layout_constraints", {}),
                    "layout": final_layout.get("layout", {}),
                    "total_area": final_layout.get("total_area", 0),
                    "facility_coordinates": final_layout.get(
                        "facility_coordinates", {}
                    ),
                    "layout_status": final_layout.get("layout_status", ""),
                    "layout_rationale": final_layout.get("layout_rationale", {}),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    if graph_name == "internet_search":
        internet_search_outcome: InternetSearchOutput = state.get(
            "internet_search_outcome"
        )
        return await ws_manager_graph.send(
            session_id,
            {
                "type": "finished",
                "graph_name": graph_name,
                "data": {
                    "system_understanding": internet_search_outcome.get(
                        "system_understanding", {}
                    ),
                    "queries": internet_search_outcome.get("queries", []),
                    "ranked_candidates": internet_search_outcome.get(
                        "ranked_candidates", {}
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    if graph_name == "overall_observer":
        return await ws_manager_graph.send(
            session_id,
            {
                "type": "finished",
                "graph_name": graph_name,
                "data": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )
