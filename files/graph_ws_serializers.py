from helpers.graph_ws_serializers_helper import _handle_internet_search, _handle_layout, _handle_overall_observer, _handle_system_definition


GRAPH_WS_SERIALIZERS = {
    "overall_observer": _handle_overall_observer,
    "system_definition": _handle_system_definition,
    "internet_search": _handle_internet_search,
    "layout": _handle_layout
}