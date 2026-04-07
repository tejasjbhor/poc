from datetime import datetime, timezone


def _handle_system_definition(node_name, payload, graph_name):

    if node_name == "INTERPRET_SYSTEM_INPUT":
        return {
            "type": "message",
            "node": node_name,
            "graph_name": graph_name,
            "data": payload.get("interpreted_input"),
        }

    if node_name == "UPDATE_SYSTEM_FUNCTIONS":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": {
                "system_description": payload.get("system_description"),
                "system_functions": payload.get("system_functions"),
                "assumptions": payload.get("assumptions"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


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


def _handle_sa_super_graph(node_name, payload, graph_name):
    if node_name == "FETCH_GRAPH_CONTEXT":
        chain = payload.get("event_chain") or []
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": {
                "event_chain_len": len(chain),
                "last_event_kind": chain[-1].get("kind")
                if chain and isinstance(chain[-1], dict)
                else None,
            },
        }

    if node_name == "SUPER_OBSERVER_LLM":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": graph_name,
            "data": {
                "next_agent": payload.get("next_agent"),
                "session_goal": payload.get("session_goal"),
                "goal_progress": payload.get("goal_progress"),
                "sa_inferred_domain": payload.get("sa_inferred_domain"),
                "sa_inferred_task": payload.get("sa_inferred_task"),
                "sa_phase": payload.get("sa_phase"),
                "sa_thoughts": payload.get("sa_thoughts"),
                "sa_checklist": payload.get("sa_checklist"),
                "sa_card": payload.get("sa_card"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
