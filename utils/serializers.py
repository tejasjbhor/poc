from datetime import datetime, timezone

from registeries.graph_ws_serializers import GRAPH_WS_SERIALIZERS


def normalize_graph_event(update, graph_name: str):

    if not update:
        return None

    if "__interrupt__" in update:
        interrupts = update["__interrupt__"]

        return {
            "type": "interrupt",
            "graph": graph_name,
            "data": [{"id": i.id, "value": i.value} for i in interrupts],
        }

    # 2. Normal node output
    node_name, payload = next(iter(update.items()))
    
    # =========================
    # GRAPH-SPECIFIC ROUTING
    # =========================
    handler = GRAPH_WS_SERIALIZERS.get(graph_name)

    if handler:
        return handler(node_name, payload, graph_name)
