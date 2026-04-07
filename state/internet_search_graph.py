from typing import TypedDict, List, Dict, Any, Optional

from state.shared_nodes_states.context_definition_node import ExecutionContext


class InternetSearchState(TypedDict):
    # --- initial input ---
    question: Optional[str]
    raw_user_input: Optional[str]

    # --- system understanding ---
    system_understanding: Dict[str, Any]

    # --- query phase ---
    queries: List[str]
    user_queries_refinment: Optional[str]

    # --- retrieval phase ---
    raw_results: Dict[str, Any]

    # --- extraction phase ---
    candidates: List[Dict[str, Any]]

    # --- ranking phase ---
    ranked_candidates: List[Dict[str, Any]]

    # --- control ---
    execution_context: ExecutionContext
    step: str
    graph_name: str
