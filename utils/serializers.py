from datetime import datetime, timezone


def normalize_graph_event(update):

    if not update:
        return None

    if "__interrupt__" in update:
        interrupts = update["__interrupt__"]

        return {
            "type": "interrupt",
            "data": [{"id": i.id, "value": i.value} for i in interrupts],
        }

    # 2. Normal node output
    node_name, payload = next(iter(update.items()))

    # 2. INTERPRETATION → show as message (NOT interrupt)
    if node_name == "INTERPRET_SYSTEM_INPUT":
        return {
            "type": "message",
            "node": node_name,
            "data": payload.get("interpreted_input"),
        }

    # 2. INTERPRETATION → show as message (NOT interrupt)
    if node_name == "UPDATE_SYSTEM_FUNCTIONS":
        return {
            "type": "data",  # ⚠️ better than "message" for structured data
            "node": node_name,
            "data": {
                "system_description": payload.get("system_description"),
                "system_functions": payload.get("system_functions"),
                "assumptions": payload.get("assumptions"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    # # 4. DEFAULT → raw node data
    # return {
    #     "type": "message",
    #     "node": node_name,
    #     "data": payload,
    # }
