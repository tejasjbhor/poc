from datetime import datetime, timezone

from api.ws_manager_graph import ws_manager_graph
from registeries.graph_ws_serializers import GRAPH_WS_SERIALIZERS


def normalize_graph_event(update, config):
    graph_name = config["configurable"]["graph_name"]

    if not update:
        return None

    if "__interrupt__" in update:
        interrupts = update["__interrupt__"]
        data = []
        graph_name = None

        for i in interrupts:
            graph_name = i.value.get("graph_name")  # assume same for all interrupts
            data.append({"id": i.id, "value": i.value.get("question")})

        return {
            "type": "interrupt",
            "graph_name": graph_name,
            "data": data,
        }

    # 2. Normal node output
    node_name, payload = next(iter(update.items()))
    # =========================
    # GRAPH-SPECIFIC ROUTING
    # =========================
    handler = GRAPH_WS_SERIALIZERS.get(payload.get("graph_name"))

    if handler:
        return handler(node_name, payload)


async def normalize_finished_event(session_id, state, graph_name):
    if graph_name == "system_definition":
        return await ws_manager_graph.send(
            session_id,
            {
                "type": "finished",
                "graph_name": graph_name,
                "data": {
                    "system_description": state.get("system_description"),
                    "system_functions": state.get("system_functions"),
                    "assumptions": state.get("assumptions"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    if graph_name == "layout":
        return await ws_manager_graph.send(
            session_id,
            {
                "type": "finished",
                "graph_name": graph_name,
                "data": {
                    "system_description": state.get("system_description", ""),
                    "system_functions": state.get("system_functions", []),
                    "assumptions": state.get("assumptions", {}),
                    "constraints": state.get("layout_constraints", {}),
                    "layout": state.get("layout", {}),
                    "total_area": state.get("total_area", 0),
                    "facility_coordinates": state.get("facility_coordinates", {}),
                    "layout_status": state.get("layout_status", ""),
                    "layout_rationale": state.get("layout_rationale", {}),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    if graph_name == "internet_search":
        return await ws_manager_graph.send(
            session_id,
            {
                "type": "finished",
                "graph_name": graph_name,
                "data": {
                    "system_understanding": state.get("system_understanding"),
                    "queries": state.get("queries"),
                    "ranked_candidates": state.get("ranked_candidates"),
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
