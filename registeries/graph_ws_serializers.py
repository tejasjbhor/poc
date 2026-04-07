from helpers.graph_ws_serializers_helper import (
    _handle_internet_search,
    _handle_layout,
    _handle_sa_super_graph,
    _handle_system_definition,
)


GRAPH_WS_SERIALIZERS = {
    "system_definition": _handle_system_definition,
    "internet_search": _handle_internet_search,
    "layout": _handle_layout,
    "sa_super_graph": _handle_sa_super_graph,
}