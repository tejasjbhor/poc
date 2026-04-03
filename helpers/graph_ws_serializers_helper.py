from datetime import datetime, timezone


def _handle_system_definition(node_name, payload, graph_name):

    # 2. INTERPRETATION → show as message (NOT interrupt)
    if node_name == "INTERPRET_SYSTEM_INPUT":
        return {
            "type": "message",
            "node": node_name,
            "graph_name": graph_name,
            "data": payload.get("interpreted_input"),
        }

    # 2. INTERPRETATION → show as message (NOT interrupt)
    if node_name == "UPDATE_SYSTEM_FUNCTIONS":
        return {
            "type": "data",  # ⚠️ better than "message" for structured data
            "node": node_name,
            "graph_name": graph_name,
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
    #     "graph_name": graph_name,
    #     "data": payload,
    # }


def _handle_internet_search(node_name, payload, graph_name):

    if node_name == "INTERPRET_SYSTEM_INPUT":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": payload.get("system_understanding"),
        }

    if node_name == "GENERATE_QUERIES":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": payload.get("queries"),
        }

    if node_name == "SEARCH_SOURCES":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": payload.get("raw_results"),
        }

    if node_name == "EXTRACT_CANDIDATES":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": payload.get("candidates"),
        }

    if node_name == "RANK_CANDIDATES":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": payload.get("ranked_candidates"),
        }

    # return {
    #     "type": "message",
    #     "node": node_name,
    #     "graph_name": graph_name,
    #     "data": payload,
    # }


def _handle_layout(node_name, payload, graph_name):

    if node_name == "NORMALIZE_INPUT":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": {
                "system_description": payload.get("system_description"),
                "system_functions": payload.get("system_functions"),
                "assumptions": payload.get("assumptions"),
            },
        }

    if node_name == "GENERATE_LAYOUT":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": {
                "layout": payload.get("layout"),
                "facility_coordinates": payload.get("facility_coordinates"),
                "layout_status": payload.get("layout_status", ""),
                "total_area": payload.get("total_area"),
                "layout_version": payload.get("layout_version"),
            },
        }

    # fallback (safety)
    # return {
    #     "type": "data",
    #     "node": node_name,
    #     "graph_name": graph_name,
    #     "data": payload,
    # }


def _handle_overall_observer(node_name, payload, graph_name):

    # 2. INTERPRETATION → show as message (NOT interrupt)
    if node_name == "INTERPRET_SYSTEM_INPUT":
        return {
            "type": "message",
            "node": node_name,
            "graph_name": graph_name,
            "data": payload.get("interpreted_input"),
        }

    # 2. INTERPRETATION → show as message (NOT interrupt)
    if node_name == "UPDATE_SYSTEM_FUNCTIONS":
        return {
            "type": "data",  # ⚠️ better than "message" for structured data
            "node": node_name,
            "graph_name": graph_name,
            "data": {
                "system_description": payload.get("system_description"),
                "system_functions": payload.get("system_functions"),
                "assumptions": payload.get("assumptions"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    if node_name == "GENERATE_QUERIES":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": payload.get("queries"),
        }

    if node_name == "SEARCH_SOURCES":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": payload.get("raw_results"),
        }

    if node_name == "EXTRACT_CANDIDATES":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": payload.get("candidates"),
        }

    if node_name == "RANK_CANDIDATES":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": payload.get("ranked_candidates"),
        }

    if node_name == "NORMALIZE_INPUT":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": {
                "system_description": payload.get("system_description"),
                "system_functions": payload.get("system_functions"),
                "assumptions": payload.get("assumptions"),
            },
        }

    if node_name == "GENERATE_LAYOUT":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": {
                "layout": payload.get("layout"),
                "facility_coordinates": payload.get("facility_coordinates"),
                "layout_status": payload.get("layout_status", ""),
                "total_area": payload.get("total_area"),
                "layout_version": payload.get("layout_version"),
            },
        }

    # return {
    #     "type": "data",
    #     "node": node_name,
    #     "graph_name": graph_name,
    #     "data": payload,
    # }
