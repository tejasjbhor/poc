from datetime import datetime, timezone

from schemas.graphs.internet_search.output import InternetSearchOutput
from schemas.graphs.layout.output import LayoutOutput
from schemas.graphs.system_definition.output import SystemDefinitionOutput


def _handle_system_definition(node_name, payload):

    if node_name == "EXECUTION_CONTEXT_DEFINITION":
        return {
            "type": "execution",
            "node": node_name,
            "graph_name": payload.get("graph_name"),
            "data": payload.get("execution_context"),
        }

    # 2. INTERPRETATION → show as message (NOT interrupt)
    if node_name == "INTERPRET_SYSTEM_INPUT":
        system_definition: SystemDefinitionOutput = payload.get("system_definition")
        return {
            "type": "data",
            "node": node_name,
            "graph_name": payload.get("graph_name"),
            "data": {
                "system_description": system_definition.system_description,
                "system_functions": system_definition.system_functions,
                "assumptions": system_definition.assumptions,
            },
        }

    # 2. INTERPRETATION → show as message (NOT interrupt)
    if node_name == "UPDATE_SYSTEM_FUNCTIONS":
        system_definition: SystemDefinitionOutput = payload.get("system_definition")
        return {
            "type": "data",  # ⚠️ better than "message" for structured data
            "node": node_name,
            "graph_name": payload.get("graph_name"),
            "data": {
                "system_description": system_definition.system_description,
                "system_functions": system_definition.system_functions,
                "assumptions": system_definition.assumptions,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    # # 4. DEFAULT → raw node data
    # return {
    #     "type": "message",
    #     "node": node_name,
    #     "graph_name": payload.get("graph_name"),
    #     "data": payload,
    # }


def _handle_internet_search(node_name, payload):

    if node_name == "EXECUTION_CONTEXT_DEFINITION":
        return {
            "type": "execution",
            "node": node_name,
            "graph_name": payload.get("graph_name"),
            "data": payload.get("execution_context"),
        }
    if node_name == "INTERPRET_SYSTEM_INPUT":
        internet_search_outcome: InternetSearchOutput = payload.get(
            "internet_search_outcome"
        )
        return {
            "type": "data",
            "node": node_name,
            "graph_name": payload.get("graph_name"),
            "data": internet_search_outcome.system_understanding,
        }

    if node_name == "GENERATE_QUERIES":
        internet_search_outcome: InternetSearchOutput = payload.get(
            "internet_search_outcome"
        )
        return {
            "type": "data",
            "node": node_name,
            "graph_name": payload.get("graph_name"),
            "data": internet_search_outcome.queries,
        }

    if node_name == "SEARCH_SOURCES":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": payload.get("graph_name"),
            "data": payload.get("raw_results"),
        }

    if node_name == "EXTRACT_CANDIDATES":
        return {
            "type": "data",
            "node": node_name,
            "graph_name": payload.get("graph_name"),
            "data": payload.get("candidates"),
        }

    if node_name == "RANK_CANDIDATES":
        internet_search_outcome: InternetSearchOutput = payload.get(
            "internet_search_outcome"
        )
        return {
            "type": "data",
            "node": node_name,
            "graph_name": payload.get("graph_name"),
            "data": internet_search_outcome.ranked_candidates,
        }

    # return {
    #     "type": "message",
    #     "node": node_name,
    #     "graph_name": payload.get("graph_name"),
    #     "data": payload,
    # }


def _handle_layout(node_name, payload):
    if node_name == "EXECUTION_CONTEXT_DEFINITION":
        return {
            "type": "execution",
            "node": node_name,
            "graph_name": payload.get("graph_name"),
            "data": payload.get("execution_context"),
        }

    if node_name == "NORMALIZE_INPUT":
        system_definition: SystemDefinitionOutput = payload.get("system_definition")

        return {
            "type": "data",
            "node": node_name,
            "graph_name": payload.get("graph_name"),
            "data": {
                "system_description": system_definition.system_description,
                "system_functions": system_definition.system_functions,
                "assumptions": system_definition.assumptions,
            },
        }

    if node_name == "GENERATE_LAYOUT":
        final_layout: LayoutOutput = payload.get("final_layout")

        return {
            "type": "data",
            "node": node_name,
            "graph_name": payload.get("graph_name"),
            "data": {
                "layout": final_layout.layout,
                "facility_coordinates": final_layout.facility_coordinates,
                "layout_status": final_layout.layout_status,
                "total_area": final_layout.total_area,
                "layout_version": "0",
            },
        }

    if node_name == "HYDRATE_LAYOUT":
        hydration_issues = payload.get("hydration_issues")
        if hydration_issues:
            return {
                "type": "message",
                "node": node_name,
                "graph_name": payload.get("graph_name"),
                "data": {
                    "message": "Missing data, requesting completion from main graph",
                    "hydration_issues": hydration_issues,
                },
            }

    # fallback (safety)
    # return {
    #     "type": "data",
    #     "node": node_name,
    #     "graph_name": payload.get("graph_name"),
    #     "data": payload,
    # }


def _handle_overall_observer(node_name, payload):
    if (
        node_name == "EXECUTION_CONTEXT_DEFINITION"
        or node_name == "NORMALIZE_EXECUTION_CONTEXT"
    ):
        return {
            "type": "execution",
            "node": node_name,
            "graph_name": payload.get("graph_name"),
            "data": payload.get("execution_context"),
        }

    if node_name == "DECIDE_ROUTE":
        hydration_issues = payload.get("hydration_issues")
        if hydration_issues:
            return {
                "type": "message",
                "node": node_name,
                "graph_name": payload.get("graph_name"),
                "data": {
                    "message": "Hydration request, from "
                    + payload.get("hydration_requester")
                    + ", rerouting to "
                    + payload.get("next_step"),
                    "requester": payload.get("hydration_requester"),
                    "hydration_issues": hydration_issues,
                    "reasoning": payload.get("reasoning"),
                    "next_step": payload.get("next_step"),
                },
            }
    # return {
    #     "type": "data",
    #     "node": node_name,
    #     "graph_name": payload.get("graph_name"),
    #     "data": payload,
    # }
