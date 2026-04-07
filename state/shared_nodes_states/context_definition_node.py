from typing import Literal, Optional, TypedDict


class ExecutionContext(TypedDict):
    mode: Literal["standalone", "subgraph", "resume", "batch"]
    source: Literal["user", "graph", "resume", "system"]
    parent_graph: Optional[str]
    current_graph: str
    root_graph: str
    depth: int
    run_id: Optional[str]  # For tracing correlation
